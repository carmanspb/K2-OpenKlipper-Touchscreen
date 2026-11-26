"""Move-page telemetry is interpolated, offset-aware and subscribed on demand."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import model
import test_service


class MotionStateTests(unittest.TestCase):
    def test_live_position_uses_gcode_frame_and_converges_to_target(self):
        status = {'toolhead': {'homed_axes': 'xyz', 'position': [310, 200, 10.2]},
                  'gcode_move': {'gcode_position': [300, 200, 10]},
                  'motion_report': {'live_position': [110, 200, 10.2]}}
        motion = model.motion_state(status)
        self.assertEqual(motion['current'], [100, 200, 10])
        self.assertEqual(motion['target'], [300, 200, 10])
        self.assertEqual(motion['moving'], [True, False, False])
        status['motion_report']['live_position'] = [310, 200, 10.2]
        self.assertEqual(model.motion_state(status)['moving'], [False]*3)

    def test_missing_or_invalid_live_position_falls_back_to_commanded(self):
        for live in (None, [], [float('nan'), 0, 0], ['bad', 0, 0]):
            status = {'gcode_move': {'gcode_position': [100, 200, 10]},
                      'toolhead': {'position': [100, 200, 10]},
                      'motion_report': {'live_position': live}}
            self.assertEqual(model.motion_state(status)['current'], [100, 200, 10])
        self.assertEqual(model.motion_state({}), {})


class MotionSubscriptionTests(unittest.TestCase):
    setUp = test_service.ServiceTests.setUp

    def test_subscribe_only_on_move_page_and_drop_old_sample_on_return(self):
        self.assertNotIn('motion_report', self.s.subscription_objects())
        self.s.submit({'action': 'view', 'page': 'move'})
        self.assertEqual(self.s.subscription_objects()['motion_report'], ['live_position'])
        self.assertTrue(self.s.subscription_refresh.is_set())
        self.s.status['motion_report'] = {'live_position': [1,2,3]}
        self.s.submit({'action': 'view', 'page': 'heat'})
        self.assertNotIn('motion_report', self.s.subscription_objects())
        self.assertNotIn('motion_report', self.s.status)
        self.assertEqual(self.s.snapshot()['motion'], {})

    def test_native_accent_is_preserved_and_new_default_is_blue(self):
        self.assertEqual(self.s.current_preferences()['accent'], '#3d8bfd')
        self.s.prefs['accent'] = '#d9434a'
        self.assertEqual(self.s.current_preferences()['accent'], '#d9434a')
