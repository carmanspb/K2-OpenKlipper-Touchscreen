/* Optional Cartographer settings. Only the backend controls the installation. */
#include "cartographer_toggle.h"
#include <stdio.h>
#include <string.h>

static bool pending, desired, failed, dismissed, timed_out;
static uint32_t started;
static uint64_t result_after;

bool cartographer_waiting(void) {
    return !timed_out && (pending || B("cartographer.busy"));
}
void cartographer_sent(const cJSON *request) {
    if (strcmp(jstr(request, "action", ""), "cartographer"))
        return;
    pending = true;
    failed = dismissed = timed_out = false;
    desired = jbool(request, "enabled", false);
    started = lv_tick_get();
    result_after = (uint64_t)N("result.id");
    snprintf(app.route, sizeof(app.route), "cartographer");
    app.dirty = true;
}
void cartographer_tick(void) {
    if (!pending && !timed_out)
        return;
    cJSON *result;
    cJSON_ArrayForEach(result, J("results")) {
        if ((uint64_t)jnum(result, "id", 0) > result_after &&
            !strcmp(jstr(result, "action", ""), "cartographer")) {
            pending = timed_out = false;
            failed = !jbool(result, "success", false);
            app.restart_waiting = false;
            app.restart_expired = false;
            app.dirty = true;
            return;
        }
    }
    if (!timed_out && (uint32_t)(lv_tick_get() - started) > 240000) {
        pending = false;
        failed = timed_out = true;
        app.dirty = true;
    }
}
static void setting_toggle(void) {
    bool enabled = B("cartographer.enabled");
    lv_obj_t *setting =
        button_fixed(app.content, "", 0, 100, 674, 96, "cartographer_toggle", false);
    lv_obj_set_style_border_width(setting, 0, 0);
    text(setting, "Cartographer", 16, 21, 530, &font_ui_20, false);
    text(setting, enabled ? "On" : "Off", 16, 52, 530, &font_ui_14, true);
    lv_obj_t *track = box(setting, 582, 28, 76, 40, false);
    lv_obj_clear_flag(track, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_radius(track, 20, 0);
    lv_obj_set_style_border_width(track, 0, 0);
    lv_obj_set_style_bg_color(track, enabled ? app.accent : lv_color_hex(0x596371), 0);
    lv_obj_t *thumb = box(track, enabled ? 39 : 5, 5, 30, 30, false);
    lv_obj_clear_flag(thumb, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_radius(thumb, 15, 0);
    lv_obj_set_style_border_width(thumb, 0, 0);
    lv_obj_set_style_bg_color(thumb, lv_color_hex(0xf0f3f7), 0);
}
void cartographer_view(void) {
    if (!B("cartographer.available")) {
        center_message("Cartographer unavailable", "A compatible installation is required.", NULL,
                       NULL);
        return;
    }
    setting_toggle();
    bool enabled = B("cartographer.enabled");
    text(app.content,
         enabled ? "PRTouch probe handles homing."
                 : "PRTouch probe handles homing and bed meshing.",
         16, 222, 642, &font_ui_20, true);
    if (enabled)
        text(app.content, "Cartographer handles bed meshing.", 16, 278, 642, &font_ui_20, true);
    const char *reason = ui_control_reason("cartographer_toggle");
    const char *error = S("cartographer.error");
    if (*error || failed)
        text(app.content,
             *error ? error : "The change could not be confirmed. Check printer status.", 16, 340,
             642, &font_ui_17, true);
    else if (*reason || B("cartographer.restart_pending"))
        text(app.content, *reason ? reason : "A previous change still needs a successful restart.",
             16, 340, 642, &font_ui_17, true);
}
bool cartographer_action(const char *action) {
    if (!strcmp(action, "cartographer_toggle")) {
        if (!B("cartographer.available") || *ui_control_reason(action))
            return true;
        bool enable = !B("cartographer.enabled");
        ui_confirm(enable
                       ? "Enable Cartographer bed scanning? Klipper will restart."
                       : "Disable Cartographer and use PRTouch bed probing? Klipper will restart.",
                   enable ? "{\"action\":\"cartographer\",\"enabled\":true,\"confirm\":true}"
                          : "{\"action\":\"cartographer\",\"enabled\":false,\"confirm\":true}");
        return true;
    }
    if (!strcmp(action, "cartographer_dismiss")) {
        dismissed = true;
        failed = false;
        app.dirty = true;
        return true;
    }
    return false;
}
bool cartographer_screen(void) {
    bool waiting = cartographer_waiting();
    bool error = !dismissed && (failed || *S("cartographer.error"));
    if (!waiting && (!error || ui_connection_mode() == CONNECTION_READY))
        return false;
    if (app.nav) {
        lv_obj_del(app.nav);
        app.nav = NULL;
    }
    lv_obj_set_pos(app.content, 0, 0);
    lv_obj_set_size(app.content, 800, 480);
    if (waiting) {
        bool enable = pending ? desired : B("cartographer.desired");
        lv_obj_t *spinner = lv_spinner_create(app.content, 1000, 70);
        lv_obj_set_pos(spinner, 368, 115);
        lv_obj_set_size(spinner, 64, 64);
        lv_obj_set_style_arc_width(spinner, 5, LV_PART_MAIN);
        lv_obj_set_style_arc_width(spinner, 5, LV_PART_INDICATOR);
        lv_obj_set_style_arc_color(spinner, lv_color_hex(0x333d4a), LV_PART_MAIN);
        lv_obj_set_style_arc_color(spinner, app.accent, LV_PART_INDICATOR);
        lv_obj_clear_flag(spinner, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_t *label =
            text(app.content, enable ? "Enabling Cartographer…" : "Disabling Cartographer…", 40,
                 218, 720, &font_heading_28, false);
        lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
        label = text(app.content, "Applying settings and restarting Klipper. Please wait.", 60, 282,
                     680, &font_ui_20, true);
        lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
    } else {
        lv_obj_t *label =
            text(app.content, "Cartographer change failed", 40, 140, 720, &font_heading_28, false);
        lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
        label = text(app.content,
                     *S("cartographer.error")
                         ? S("cartographer.error")
                         : "The operation timed out. Check printer status before retrying.",
                     80, 210, 640, &font_ui_20, true);
        lv_obj_set_style_text_align(label, LV_TEXT_ALIGN_CENTER, 0);
        button_fixed(app.content, "Close", 260, 370, 280, 64, "cartographer_dismiss", false);
    }
    return true;
}
