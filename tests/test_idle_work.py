"""Idle caches and startup file preparation preserve live safety and file changes."""
import unittest
from unittest import mock

import test_service
import action_policy
import model
import storage


class IdleWorkTests(unittest.TestCase):
    def setUp(self):
        fixture = test_service.ServiceTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.s, self.mr = fixture.s, fixture.mr

    def test_limits_cached_and_configuration_and_offsets_invalidate(self):
        with mock.patch('model.heater_limits', wraps=model.heater_limits) as heater, \
             mock.patch('model.axis_limits', wraps=model.axis_limits) as axis:
            first = self.s.snapshot()
            count = heater.call_count
            self.s.snapshot()
            self.assertEqual(heater.call_count, count)
            self.assertEqual(axis.call_count, 3)
            self.s.settings['extruder']['max_temp'] = 300
            self.assertEqual(self.s.snapshot()['heaters'][0]['limits']['maximum'], 300)
            self.assertEqual(heater.call_count, count + 1)
            self.s.status['gcode_move']['gcode_position'][0] -= 5
            changed = self.s.snapshot()
            self.assertEqual(changed['axes']['x']['maximum'], first['axes']['x']['maximum'] - 5)
            self.assertEqual(axis.call_count, 6)

    def test_availability_ignores_telemetry_but_tracks_interlocks(self):
        with mock.patch('action_policy.availability', wraps=action_policy.availability) as availability:
            self.s.snapshot()
            self.s.status['extruder'] = {'temperature': 100}
            self.s.status['toolhead']['print_time'] = 10
            self.s.snapshot()
            self.assertEqual(availability.call_count, 1)
            self.s.status['toolhead']['homed_axes'] = ''
            self.assertFalse(self.s.snapshot()['availability']['jog:X']['enabled'])
            self.assertEqual(availability.call_count, 2)
            self.s.status['print_stats']['state'] = 'printing'
            self.assertFalse(self.s.snapshot()['availability']['home']['enabled'])
            self.s.connected = False
            self.assertFalse(self.s.snapshot()['availability']['temperature:extruder']['enabled'])

    def test_availability_matches_uncached_policy_for_state_transitions(self):
        for object_name, field, values in [
            ('webhooks', 'state', ['ready', 'shutdown']),
            ('print_stats', 'state', ['standby', 'printing', 'paused']),
            ('print_stats', 'filename', ['a.gcode', 'b.gcode']),
            ('toolhead', 'homed_axes', ['', 'xy', 'xyz']),
            ('k2_cfs', 'active_slot', ['', 'A']),
            ('k2_cfs', 'change_pending', [True, False]),
            ('k2_cfs', 'filament_activity', [{'action':'load'}, {'action':'unload'}, {}]),
            ('filament_switch_sensor filament_sensor', 'filament_detected', [True, False]),
        ]:
            for value in values:
                self.s.status[object_name][field] = value
                self.assertEqual(self.s.snapshot()['availability'],
                                 action_policy.availability(self.s.status, self.s.connected, self.s.operations.values()))
        self.s.operations[1] = {'id':1, 'action':'home', 'resources':['motion'], 'label':'Homing'}
        self.assertEqual(self.s.snapshot()['availability'],
                         action_policy.availability(self.s.status, True, self.s.operations.values()))
        self.s.operations.clear()
        self.assertTrue(self.s.snapshot()['availability']['restart']['enabled'])

    def test_file_preload_can_start_before_motor_readiness(self):
        self.s.status['webhooks']['state'] = 'startup'
        self.s.status['k2_motor_bus'] = {'motors_ready':False}
        with mock.patch.object(self.s, 'submit') as submit:
            self.s.preload_files()
        submit.assert_called_once_with({'action':'files', 'source':'gcodes', 'automatic':True})

    def test_initial_listing_does_not_load_any_thumbnails(self):
        self.mr.files.return_value = [{'path':f'{i}.gcode','modified':i,'size':10} for i in range(100)]
        with mock.patch.object(self.s, 'file_thumbnails') as thumbnails:
            self.s.execute({'action':'files'})
        self.assertEqual(len(self.s.files), 100)
        thumbnails.assert_not_called()

    def test_worker_only_loads_requested_window_and_stops_on_navigation(self):
        self.s.visible_page = 'files'
        self.s.files = [{'path':str(i)} for i in range(100)]
        with mock.patch('service.threading.Thread'):
            self.s.request_file_thumbnails(20, 7)
        with mock.patch.object(self.s, 'file_thumbnails') as thumbnails:
            self.s.thumbnail_worker()
        self.assertEqual([call.args[0][0]['path'] for call in thumbnails.call_args_list], [str(i) for i in range(20,27)])
        self.s.thumbnail_pending = (self.s.files[:7], self.s.file_generation)
        self.s.thumbnail_running = True
        self.s.visible_page = 'home'
        with mock.patch.object(self.s, 'file_thumbnails') as thumbnails:
            self.s.thumbnail_worker()
        thumbnails.assert_not_called()
        self.assertFalse(self.s.thumbnail_running)

    def test_refresh_preserves_unchanged_preview_and_removes_changed_or_deleted(self):
        self.s.file_signatures = {'same.gcode':(1,10), 'changed.gcode':(1,10), 'deleted.gcode':(1,10)}
        self.s.platform['file_thumbnails'] = {key:key+'.png' for key in self.s.file_signatures}
        self.mr.files.return_value = [{'path':'same.gcode','modified':1,'size':10}, {'path':'changed.gcode','modified':2,'size':10}]
        self.s.execute({'action':'files'})
        self.assertEqual(self.s.platform['file_thumbnails'], {'same.gcode':'same.gcode.png'})

    def test_file_events_update_listing_without_http_and_invalidate_preview(self):
        self.s.files = [{'path':'old.gcode','modified':1,'size':10}]
        self.s.file_signatures['old.gcode'] = (1,10)
        self.s.platform['file_thumbnails'] = {'old.gcode':'old.png'}
        self.s.stream_message({'method':'notify_filelist_changed','params':[{
            'action':'move_file', 'source_item':{'root':'gcodes','path':'old.gcode'},
            'item':{'root':'gcodes','path':'new.gcode','modified':2,'size':10}}]})
        self.assertEqual([f['path'] for f in self.s.files], ['new.gcode'])
        self.assertEqual(self.s.platform['file_thumbnails'], {})
        self.mr.files.assert_not_called()
        self.s.filelist_changed({'action':'move_file', 'source_item':{'root':'gcodes','path':'new.gcode'},
                                 'item':{'root':'config','path':'other.gcode','modified':2,'size':10}})
        self.assertEqual(self.s.files, [])

    def test_events_during_listing_are_replayed(self):
        self.s.files_refreshing = True
        def listing():
            self.s.filelist_changed({'action':'create_file','item':{'root':'gcodes','path':'new.gcode','modified':2,'size':20}})
            return [{'path':'old.gcode','modified':1,'size':10}]
        self.mr.files.side_effect = listing
        self.s.execute({'action':'files'})
        self.assertEqual([f['path'] for f in self.s.files], ['new.gcode','old.gcode'])

    def test_directory_change_requests_reconciliation(self):
        self.s.files_preloaded = True
        self.s.filelist_changed({'action':'move_dir', 'item':{'root':'gcodes','path':'new'}})
        self.assertFalse(self.s.files_preloaded)
        self.assertTrue(self.s.files_need_refresh)

    def test_static_platform_commands_are_not_run_every_refresh(self):
        with mock.patch('storage.system_identity', return_value={}), \
             mock.patch('service.platform.usb_disk', return_value=None), \
             mock.patch.object(self.s.wifi, 'status', return_value={}), \
             mock.patch('service.platform.system_zone', return_value='UTC') as zone, \
             mock.patch('service.subprocess.check_output', return_value=b'version=1\n') as command, \
             mock.patch.object(self.s, 'prepare_artwork'), \
             mock.patch.object(self.s, 'prepare_icons'):
            self.s.refresh_platform()
            self.s.refresh_platform()
            zone.assert_called_once()
            command.assert_called_once()
            self.assertEqual(self.s.platform['stock_firmware'], '1')

    def test_preview_failures_back_off_and_new_file_retries_immediately(self):
        self.s.status['print_stats']['filename'] = 'bad.gcode'
        with mock.patch.object(self.s, 'refresh_print_preview', return_value=False) as refresh:
            self.s.preload_print_preview(100)
            self.s.preload_print_preview(103)
            refresh.assert_called_once()
            self.s.preload_print_preview(106)
            self.assertEqual(refresh.call_count, 2)
            self.s.status['print_stats']['filename'] = 'new.gcode'
            self.s.preload_print_preview(107)
            self.assertEqual(refresh.call_count, 3)

    def test_missing_catalogue_does_not_query_each_poll(self):
        self.mr.request.return_value = {'status': {'hark_cfs_slots': {}}}
        with mock.patch('service.time.monotonic', return_value=100):
            self.s.refresh_catalogue()
            self.s.refresh_catalogue()
        self.mr.request.assert_called_once()
        self.s.status_epoch += 1
        self.s.refresh_catalogue()
        self.assertEqual(self.mr.request.call_count, 2)

    def test_live_file_events_allow_opening_cached_list_without_http(self):
        self.s.stream_connected = True
        self.s.files_refreshed_at = 1
        with mock.patch('service.threading.Thread') as thread:
            self.s.submit({'action':'files','automatic':True})
            thread.assert_not_called()
            self.s.files_need_refresh = True
            self.s.submit({'action':'files','automatic':True})
            thread.assert_called_once()

    def test_live_renderer_requests_bounded_file_window(self):
        import json
        import socket
        import subprocess
        from pathlib import Path
        binary = Path(__file__).resolve().parents[1] / 'out/host/openklipper-screen'
        if not binary.exists():
            self.skipTest('Build the native application before IPC tests')
        path = str(self.s.config_path.parent / 'screen.sock')
        snapshot = self.s.snapshot()
        self.s.files = [{'path':f'{i}.gcode','modified':i,'size':10} for i in range(100)]
        snapshot['files'] = self.s.files
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(server.close)
        server.bind(path)
        server.listen(1)
        server.settimeout(5)
        process = subprocess.Popen([str(binary), '--headless', '--socket', path, '--page', 'files',
                                    '--assets', str(binary.parents[2] / 'assets/generated')],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        def stop():
            process.terminate()
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
        self.addCleanup(stop)
        connection, _ = server.accept()
        self.addCleanup(connection.close)
        connection.settimeout(5)
        connection.sendall(json.dumps(snapshot).encode() + b'\n')
        reader = connection.makefile('rb')
        self.addCleanup(reader.close)
        for _ in range(10):
            request = json.loads(reader.readline())
            if request.get('action') == 'file_window':
                self.assertEqual(request, {'action':'file_window', 'first':0, 'count':7})
                break
        else:
            self.fail('Renderer did not request the visible file window')


if __name__ == '__main__':
    unittest.main()