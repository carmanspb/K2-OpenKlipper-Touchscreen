"""Discovered by tests/test_cartographer_toggle.py in the normal full suite."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import action_policy
import cartographer_toggle as feature
from test_service import Service, settings, status


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.integration = feature.Integration(self.root)

    def write(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def installed(self, enabled=True):
        i = self.integration
        self.write(i.repo / "plugin-lock.json", "{}")
        for name in ("k2ctl.py", "setup.py", "usb.py", "bridge.py", "firmware.py"):
            self.write(i.repo / "scripts" / name, "# test controller\n")
        self.write(
            i.repo / "config/lifecycle.json",
            json.dumps({"hardware": "cartographer-v3", "runtime_serial": "TEST_ONLY"}),
        )
        self.override = self.root / "config/printer-overrides.cfg"
        self.stub = self.root / "build/klippy/extras/cartographer.py"
        self.write(
            self.stub,
            "# Managed by k2-openklipper-cartographer\nimport sys\nsys.path.insert(0, "
            + repr(str(i.addon / "vendor"))
            + ")\nfrom cartographer.extra import load_config\n",
        )
        self.write(
            i.addon / "manifest.json",
            json.dumps(
                {
                    "override": str(self.override),
                    "stub": str(self.stub),
                    "stub_sha256": hashlib.sha256(self.stub.read_bytes()).hexdigest(),
                    "plugin": "test-version",
                }
            ),
        )
        self.write(i.addon / "vendor/cartographer/extra.py", "# installed plugin\n")
        self.switch(enabled)

    def switch(self, enabled, pending=False):
        self.write(
            self.integration.control / "lifecycle.json",
            json.dumps({"enabled": enabled, "restart_pending": pending}),
        )
        line = (
            "[include cartographer-mesh.cfg]" if enabled else "# Cartographer disabled"
        )
        self.write(
            self.override, feature.BEGIN + "\n" + line + "\n" + feature.END + "\n"
        )

    def test_absent_and_foreign_installations_are_hidden(self):
        self.assertEqual(self.integration.inspect(), {"available": False})
        self.installed()
        self.stub.write_text("# unmanaged installation")
        self.assertFalse(self.integration.inspect()["available"])

    def test_enabled_and_disabled_are_read_from_owned_configuration(self):
        self.installed()
        self.assertEqual(
            self.integration.inspect(),
            {"available": True, "enabled": True, "restart_pending": False},
        )
        self.switch(False)
        self.assertFalse(self.integration.inspect()["enabled"])

    def test_malformed_or_inconsistent_state_is_hidden(self):
        self.installed()
        self.write(self.integration.control / "lifecycle.json", "{")
        self.assertFalse(self.integration.inspect()["available"])
        self.switch(False)
        self.write(self.integration.control / "lifecycle.json", '{"enabled":true}')
        self.assertFalse(self.integration.inspect()["available"])

    def test_missing_controller_is_hidden_but_addon_updates_are_accepted(self):
        self.installed()
        self.write(self.integration.repo / "scripts/k2ctl.py", "# updated controller")
        manifest_path = self.integration.addon / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["plugin"] = "next-release"
        manifest_path.write_text(json.dumps(manifest))
        self.assertTrue(self.integration.inspect()["available"])
        (self.integration.repo / "scripts/k2ctl.py").unlink()
        self.assertFalse(self.integration.inspect()["available"])

    def test_apply_uses_only_existing_lifecycle_command_and_checks_result(self):
        self.installed()

        def run(command, **kwargs):
            self.assertEqual(command[2], "disable")
            self.assertIn("--apply", command)
            self.assertNotIn("shell", kwargs)
            self.assertEqual(kwargs["timeout"], 110)
            self.switch(False)
            return mock.Mock(returncode=0)

        with mock.patch.object(feature.subprocess, "run", side_effect=run) as run_mock:
            result = self.integration.apply(False, "http://127.0.0.1:7126")
        self.assertFalse(result["enabled"])
        self.assertEqual(run_mock.call_count, 1)

    def test_command_failure_and_pending_restart_are_not_success(self):
        self.installed()
        with mock.patch.object(
            feature.subprocess,
            "run",
            return_value=mock.Mock(returncode=1, stderr="test failure", stdout=""),
        ):
            with self.assertRaisesRegex(RuntimeError, "test failure"):
                self.integration.apply(False, "http://localhost")
        self.switch(False, pending=True)
        with mock.patch.object(
            feature.subprocess, "run", return_value=mock.Mock(returncode=0)
        ):
            with self.assertRaisesRegex(RuntimeError, "could not be verified"):
                self.integration.apply(False, "http://localhost")


class PolicyTests(unittest.TestCase):
    def test_toggle_blocks_prints_initialization_motion_and_other_operations(self):
        base = status()
        self.assertEqual(feature.blocked(base, True, []), "")
        for state in ("printing", "paused", None):
            changed = copy.deepcopy(base)
            changed["print_stats"]["state"] = state
            self.assertTrue(
                action_policy.reason({"action": "cartographer"}, changed, True, [])
            )
        for key, value in (
            ("idle_timeout", {"state": "Printing"}),
            ("k2_motor_bus", {"motors_ready": False}),
        ):
            changed = dict(base, **{key: value})
            self.assertTrue(feature.blocked(changed, True, []))
        operation = {"action": "temperature", "label": "Heating", "resources": ["bed"]}
        self.assertTrue(
            action_policy.reason({"action": "cartographer"}, base, True, [operation])
        )

    def test_all_other_mutations_are_blocked_during_toggle(self):
        operation = {
            "action": "cartographer",
            "label": "Changing Cartographer",
            "resources": ["*"],
        }
        for action in action_policy.ACTIONS:
            if action in ("temperature", "fan", "preference"):
                continue
            with self.subTest(action=action):
                self.assertTrue(
                    action_policy.reason(
                        {"action": action}, status(), True, [operation]
                    )
                )

    def test_availability_cache_tracks_motor_and_motion_state(self):
        base = status()
        before = action_policy.availability_inputs(base, True, [])
        for key, value in (
            ("idle_timeout", {"state": "Printing"}),
            ("k2_motor_bus", {"motors_ready": False}),
        ):
            self.assertNotEqual(
                before,
                action_policy.availability_inputs(dict(base, **{key: value}), True, []),
            )


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        config = Path(self.tmp.name) / "native.cfg"
        config.write_text("[brand]\nmodel: Test printer\n[screen]\n")
        self.mr = mock.Mock(base="http://127.0.0.1:7126")
        self.s = Service(config, self.mr)
        self.s.status, self.s.settings, self.s.connected = status(), settings(), True
        self.s.cartographer = mock.Mock()
        self.s.cartographer.inspect.return_value = {
            "available": True,
            "enabled": False,
            "restart_pending": False,
        }
        self.s.refresh_cartographer()
        self.s.fresh = mock.Mock(return_value=(status(), settings()))

    def test_installation_is_checked_at_startup_not_on_navigation_or_snapshots(self):
        config = Path(self.tmp.name) / "startup.cfg"
        config.write_text("[brand]\nmodel: Test printer\n[screen]\n")
        with mock.patch.object(
            feature.Integration, "inspect", return_value={"available": False}
        ) as inspect:
            service = Service(config, self.mr)
            service.status, service.settings, service.connected = (
                status(),
                settings(),
                True,
            )
            for _ in range(5):
                service.snapshot()
                service.screen_snapshot()
                service.submit({"action": "view", "page": "settings"})
                service.submit({"action": "view", "page": "cartographer"})
            self.assertEqual(inspect.call_count, 1)

    def test_busy_rejection_acknowledges_without_reserving_or_starting_operation(self):
        self.s.operation_id = 7
        existing = {
            "id": 7,
            "action": "home",
            "label": "Homing",
            "resources": ["motion"],
        }
        self.s.operations[7] = existing
        with self.assertRaises(action_policy.ActionBusy):
            self.s.submit({"action": "cartographer", "enabled": True, "confirm": True})
        result = self.s.snapshot()["result"]
        self.assertEqual(result["id"], 8)
        self.assertTrue(result["rejected"])
        self.assertFalse(result["success"])
        self.assertEqual(result["action"], "cartographer")
        self.assertEqual(self.s.operations, {7: existing})
        self.assertFalse(self.s.cartographer_state["busy"])
        self.assertFalse(self.s.cartographer_state["enabled"])
        self.assertEqual(self.s.cartographer_state["error"], result["error"])
        self.s.cartographer.apply.assert_not_called()
        self.s.fresh.assert_not_called()

    def test_confirmation_and_boolean_are_required_before_mutation(self):
        for request in ({"enabled": True}, {"confirm": True, "enabled": "true"}):
            with self.assertRaises(ValueError):
                self.s.execute(dict(action="cartographer", **request))
        self.s.cartographer.apply.assert_not_called()

    def test_success_is_published_only_after_runtime_verification(self):
        def apply(enabled, _):
            self.assertTrue(self.s.snapshot()["cartographer"]["busy"])
            self.s.cartographer.inspect.return_value = {
                "available": True,
                "enabled": enabled,
                "restart_pending": False,
            }

        self.s.cartographer.apply.side_effect = apply
        with mock.patch.object(feature, "verify_runtime") as verify:
            self.s.execute({"action": "cartographer", "enabled": True, "confirm": True})
        verify.assert_called_once_with(self.mr, True)
        self.assertEqual(
            self.s.snapshot()["cartographer"],
            {
                "available": True,
                "enabled": True,
                "restart_pending": False,
                "busy": False,
            },
        )

    def test_failure_keeps_actual_state_and_releases_busy(self):
        self.s.cartographer.apply.side_effect = RuntimeError("restart failed")
        with self.assertRaisesRegex(RuntimeError, "restart failed"):
            self.s.execute({"action": "cartographer", "enabled": True, "confirm": True})
        state = self.s.snapshot()["cartographer"]
        self.assertFalse(state["enabled"])
        self.assertFalse(state["busy"])
        self.assertEqual(state["error"], "restart failed")

    def test_fresh_printing_status_blocks_stale_idle_request(self):
        busy = status()
        busy["print_stats"]["state"] = "printing"
        self.s.fresh.return_value = busy, settings()
        with self.assertRaises(action_policy.ActionBusy):
            self.s.execute({"action": "cartographer", "enabled": True, "confirm": True})
        self.s.cartographer.apply.assert_not_called()

    def test_missing_installation_disables_control_and_rejects_submit(self):
        self.s.cartographer.inspect.return_value = {"available": False}
        self.s.refresh_cartographer()
        self.assertFalse(self.s.snapshot()["cartographer"]["available"])
        with self.assertRaises(action_policy.ActionBusy):
            self.s.submit({"action": "cartographer", "enabled": True, "confirm": True})

    def test_runtime_waits_for_configuration_and_motor_initialization(self):
        self.mr.query.side_effect = [
            dict(status(), k2_motor_bus={"motors_ready": False}),
            status(),
        ]
        self.mr.settings.return_value = {"cartographer": {}, "mcu cartographer": {}}
        with mock.patch.object(feature.time, "sleep"):
            feature.verify_runtime(self.mr, True)
        self.assertEqual(self.mr.query.call_count, 2)
        with mock.patch.object(feature.time, "monotonic", side_effect=[0, 1]):
            with self.assertRaisesRegex(RuntimeError, "did not return"):
                feature.verify_runtime(self.mr, True, timeout=0.1)


class NativeToggleTests(unittest.TestCase):
    def setUp(self):
        import test_native_ui

        if not test_native_ui.BINARY.exists():
            self.skipTest("Build the native application before UI tests")
        self.ui = test_native_ui.NativeUI()
        self.ui.setUp()
        self.addCleanup(self.ui.doCleanups)
        self.data = self.ui.data
        self.data["cartographer"] = {"available": True, "enabled": False, "busy": False}
        self.data["availability"]["cartographer"] = {"enabled": True, "reason": ""}

    def test_settings_entry_is_hidden_unless_compatible(self):
        for available in (False, True):
            self.data["cartographer"]["available"] = available
            items, _ = self.ui.render("settings", data=self.data)
            rows = [i for i in items if i["action"] == "route:cartographer"]
            self.assertEqual(bool(rows), available)
            if rows:
                self.assertLessEqual(rows[0]["rect"][1] + rows[0]["rect"][3], 480)

    def test_disabled_control_never_opens_confirmation(self):
        self.data["availability"]["cartographer"] = {
            "enabled": False,
            "reason": "Unavailable during printing",
        }
        items, commands = self.ui.render(
            "cartographer", ["cartographer_toggle", "confirmed"], self.data
        )
        toggle = next(i for i in items if i["action"] == "cartographer_toggle")
        self.assertFalse(toggle["enabled"])
        self.assertEqual(commands, [])

    def test_cancel_keeps_state_and_confirmation_sends_exactly_once(self):
        _, commands = self.ui.render(
            "cartographer", ["cartographer_toggle", "close"], self.data
        )
        self.assertEqual(commands, [])
        for enabled in (True, False):
            self.data["cartographer"]["enabled"] = enabled
            items, commands = self.ui.render(
                "cartographer",
                ["cartographer_toggle", "confirmed", "confirmed"],
                self.data,
            )
            self.assertEqual(
                commands,
                [{"action": "cartographer", "enabled": not enabled, "confirm": True}],
            )
            self.assertEqual(items, [])  # Operation screen has no actionable controls.

    def test_expected_disconnect_stays_on_operation_screen_and_returns_to_setting(self):
        steps = ["cartographer_toggle", "confirmed"]
        lost = copy.deepcopy(self.data)
        lost["connected"] = False
        lost["status"]["webhooks"]["state"] = "startup"
        lost["cartographer"].update(busy=True, desired=True)
        items, _ = self.ui.render(
            "cartographer", steps + [{"snapshot": lost}], self.data
        )
        self.assertEqual(items, [])  # No generic recovery/restart buttons.
        ready = copy.deepcopy(self.data)
        ready["cartographer"]["enabled"] = True
        ready["printer_generation"] = 1
        ready["results"] = [{"id": 1, "action": "cartographer", "success": True}]
        ready["result"] = ready["results"][0]
        items, _ = self.ui.render(
            "cartographer", steps + [{"snapshot": lost}, {"snapshot": ready}], self.data
        )
        self.assertTrue(any(i["action"] == "cartographer_toggle" for i in items))
        self.assertFalse(any(i["action"] == "open_files" for i in items))

    def test_rejected_request_immediately_restores_settings_controls(self):
        rejected = copy.deepcopy(self.data)
        rejected["status"]["print_stats"]["state"] = "printing"
        rejected["availability"]["cartographer"] = {
            "enabled": False,
            "reason": "Unavailable during printing",
        }
        rejected["cartographer"]["error"] = "Unavailable during printing"
        rejected["results"] = [
            {
                "id": 1,
                "action": "cartographer",
                "success": False,
                "rejected": True,
                "error": "Unavailable during printing",
            }
        ]
        rejected["result"] = rejected["results"][0]
        items, commands = self.ui.render(
            "cartographer",
            ["cartographer_toggle", "confirmed", {"snapshot": rejected}],
            self.data,
        )
        toggle = next(i for i in items if i["action"] == "cartographer_toggle")
        self.assertFalse(toggle["enabled"])
        self.assertTrue(any(i["action"] == "back" for i in items))
        self.assertEqual(
            commands, [{"action": "cartographer", "enabled": True, "confirm": True}]
        )

    def test_unrelated_connection_loss_still_has_normal_recovery(self):
        lost = copy.deepcopy(self.data)
        lost["connected"] = False
        items, _ = self.ui.render("cartographer", [{"snapshot": lost}], self.data)
        self.assertEqual(
            {i["action"] for i in items}, {"restart:klipper", "restart:firmware"}
        )

    def test_failed_operation_has_specific_recovery_and_timeout_is_bounded(self):
        failed = copy.deepcopy(self.data)
        failed["connected"] = False
        failed["cartographer"]["error"] = "Test restart failure"
        failed["results"] = [{"id": 1, "action": "cartographer", "success": False}]
        failed["result"] = failed["results"][0]
        steps = ["cartographer_toggle", "confirmed"]
        items, _ = self.ui.render(
            "cartographer", steps + [{"snapshot": failed}], self.data
        )
        self.assertTrue(any(i["action"] == "cartographer_dismiss" for i in items))
        lost = copy.deepcopy(self.data)
        lost["connected"] = False
        lost["cartographer"].update(busy=True, desired=True)
        items, _ = self.ui.render(
            "cartographer",
            steps + [{"snapshot": lost}, {"advance_ms": 240001}],
            self.data,
        )
        self.assertTrue(any(i["action"] == "cartographer_dismiss" for i in items))


class PackagingTests(unittest.TestCase):
    def test_feature_runtime_is_fingerprinted_but_tests_and_docs_are_not(self):
        import test_package_installation as packaging

        fixture = packaging.PackageChecks()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        folder = fixture.source / "features/cartographer-toggle"
        (folder / "tests").mkdir(parents=True)
        (folder / "cartographer_toggle.py").write_text("# runtime")
        (folder / "cartographer_toggle.c").write_text("/* renderer */")
        (folder / "tests/test_toggle.py").write_text("# tests")
        (folder / "README.md").write_text("documentation")
        inputs = packaging.package_check.source_inputs(fixture.source)
        self.assertIn(
            "touchscreen/features/cartographer-toggle/cartographer_toggle.py", inputs
        )
        self.assertIn(
            "touchscreen/features/cartographer-toggle/cartographer_toggle.c", inputs
        )
        self.assertFalse(
            any("/tests/" in name or name.endswith("README.md") for name in inputs)
        )


class SocketRejectionTests(unittest.TestCase):
    def test_stale_idle_toggle_gets_rejection_through_real_socket_handler(self):
        import test_state_updates

        for scenario in ("printing", "movement", "operation"):
            with self.subTest(scenario=scenario):
                fixture = test_state_updates.StateUpdates()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                service = fixture.s
                service.cartographer_state = {
                    "available": True,
                    "enabled": False,
                    "busy": False,
                }
                peer, reader, baseline = fixture.connect()
                self.assertTrue(baseline["availability"]["cartographer"]["enabled"])
                with service.lock:
                    if scenario == "printing":
                        service.status = dict(
                            service.status, print_stats={"state": "printing"}
                        )
                    elif scenario == "movement":
                        service.status = dict(
                            service.status, idle_timeout={"state": "Printing"}
                        )
                    else:
                        service.operations[3] = {
                            "id": 3,
                            "action": "home",
                            "resources": ["motion"],
                            "label": "Homing",
                        }
                        service.operation_id = 3
                    service.changed()
                with mock.patch.object(service, "execute") as execute:
                    peer.sendall(
                        b'{"action":"cartographer","enabled":true,"confirm":true}\n'
                    )
                    for _ in range(5):
                        patch = json.loads(reader.readline())
                        result = patch.get("set", patch).get("result")
                        if result and result.get("rejected"):
                            break
                    else:
                        self.fail("Backend did not acknowledge the rejected toggle")
                    self.assertFalse(result["success"])
                    self.assertEqual(result["action"], "cartographer")
                    self.assertTrue(result["error"])
                    self.assertFalse(service.cartographer_state["busy"])
                    execute.assert_not_called()
