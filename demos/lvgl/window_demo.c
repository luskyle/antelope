#include <SDL.h>
#include <lvgl.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define WINDOW_WIDTH 1080
#define WINDOW_HEIGHT 680
#define DRAW_BUFFER_LINES 48

static SDL_Renderer *renderer;
static SDL_Window *app_window;
static SDL_Texture *display_texture;
static lv_obj_t *click_count_label;
static lv_obj_t *slider_value_label;
static lv_obj_t *runtime_label;
static lv_obj_t *nav_buttons[3];
static lv_obj_t *pages[3];
static lv_obj_t *activity_bars[8];
static lv_obj_t *cpu_bar;
static lv_obj_t *memory_bar;
static lv_obj_t *cpu_value_label;
static lv_obj_t *memory_value_label;
static lv_obj_t *telemetry_chart;
static lv_chart_series_t *cpu_series;
static lv_chart_series_t *memory_series;
static lv_obj_t *component_status_label;
static lv_timer_t *dashboard_timer;
static uint32_t click_count;
static uint32_t animation_phase;
static bool live_updates = true;

static lv_color_t color(uint32_t hex)
{
    return lv_color_hex(hex);
}

static void style_panel(lv_obj_t *obj, uint32_t background)
{
    lv_obj_set_style_bg_color(obj, color(background), 0);
    lv_obj_set_style_bg_opa(obj, LV_OPA_COVER, 0);
    lv_obj_set_style_border_width(obj, 0, 0);
    lv_obj_set_style_radius(obj, 16, 0);
    lv_obj_set_style_pad_all(obj, 0, 0);
    lv_obj_set_scrollable(obj, false);
}

static lv_obj_t *make_label(lv_obj_t *parent, const char *text, int x, int y,
                            uint32_t text_color)
{
    lv_obj_t *label = lv_label_create(parent);
    lv_label_set_text(label, text);
    lv_obj_set_style_text_color(label, color(text_color), 0);
    lv_obj_align(label, LV_ALIGN_TOP_LEFT, x, y);
    return label;
}

static lv_obj_t *make_panel(lv_obj_t *parent, int x, int y, int width,
                            int height, uint32_t background)
{
    lv_obj_t *panel = lv_obj_create(parent);
    lv_obj_set_size(panel, width, height);
    lv_obj_set_pos(panel, x, y);
    style_panel(panel, background);
    return panel;
}

static void on_demo_button(lv_event_t *event)
{
    (void)event;
    click_count++;

    char value[32];
    snprintf(value, sizeof(value), "%u", click_count);
    lv_label_set_text(click_count_label, value);
}

static void on_slider_changed(lv_event_t *event)
{
    lv_obj_t *slider = lv_event_get_target_obj(event);
    char value[32];
    int speed = (int)lv_slider_get_value(slider);
    snprintf(value, sizeof(value), "%d%%", speed);
    lv_label_set_text(slider_value_label, value);
    if (dashboard_timer != NULL) {
        lv_timer_set_period(dashboard_timer, (uint32_t)(2000 - speed * 18));
    }
}

static void select_page(uint32_t page_index)
{
    static const char *page_names[] = {"Overview", "Performance", "Components"};
    if (page_index >= 3) return;

    for (uint32_t i = 0; i < 3; i++) {
        lv_obj_set_hidden(pages[i], i != page_index);
        lv_obj_set_style_bg_color(
            nav_buttons[i],
            color(i == page_index ? 0x1D2C43 : 0x0E1728),
            LV_PART_MAIN
        );
    }

    SDL_SetWindowTitle(app_window, page_names[page_index]);
}

static void on_nav_clicked(lv_event_t *event)
{
    uint32_t page_index = (uint32_t)(uintptr_t)lv_event_get_user_data(event);
    select_page(page_index);
}

static void on_live_updates_changed(lv_event_t *event)
{
    lv_obj_t *toggle = lv_event_get_target_obj(event);
    live_updates = lv_obj_has_state(toggle, LV_STATE_CHECKED);
    lv_label_set_text(
        component_status_label,
        live_updates ? "Telemetry is updating" : "Telemetry is paused"
    );
}

static void on_reset_clicked(lv_event_t *event)
{
    (void)event;
    click_count = 0;
    lv_label_set_text(click_count_label, "0");
}

static void update_dashboard(lv_timer_t *timer)
{
    (void)timer;
    if (!live_updates) return;

    animation_phase++;

    char value[32];
    snprintf(value, sizeof(value), "%u ms", 16 + animation_phase % 9);
    lv_label_set_text(runtime_label, value);
    int cpu = 24 + (int)((animation_phase * 17) % 58);
    int memory = 48 + (int)((animation_phase * 7) % 42);
    snprintf(value, sizeof(value), "%d%%", cpu);
    lv_label_set_text(cpu_value_label, value);
    snprintf(value, sizeof(value), "%d%%", memory);
    lv_label_set_text(memory_value_label, value);
    lv_bar_set_value(cpu_bar, cpu, LV_ANIM_ON);
    lv_bar_set_value(memory_bar, memory, LV_ANIM_ON);
    lv_chart_set_next_value(
        telemetry_chart,
        cpu_series,
        20 + (int)((animation_phase * 19) % 70)
    );
    lv_chart_set_next_value(
        telemetry_chart,
        memory_series,
        35 + (int)((animation_phase * 11) % 60)
    );

    for (uint32_t i = 0; i < 8; i++) {
        int height = 28 + (int)((animation_phase * (i + 3) * 7 + i * 19) % 78);
        lv_obj_set_height(activity_bars[i], height);
        lv_obj_align(activity_bars[i], LV_ALIGN_BOTTOM_LEFT, 18 + (int)i * 56, 0);
    }
}

static lv_obj_t *make_nav_button(lv_obj_t *parent, const char *text, int y,
                                 uint32_t page_index)
{
    lv_obj_t *button = lv_button_create(parent);
    lv_obj_set_size(button, 164, 42);
    lv_obj_set_pos(button, 14, y);
    lv_obj_set_style_bg_color(button, color(0x0E1728), LV_PART_MAIN);
    lv_obj_set_style_bg_color(button, color(0x1D2C43), LV_PART_MAIN | LV_STATE_PRESSED);
    lv_obj_set_style_border_width(button, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(button, 10, LV_PART_MAIN);
    lv_obj_add_event_cb(
        button,
        on_nav_clicked,
        LV_EVENT_CLICKED,
        (void *)(uintptr_t)page_index
    );

    lv_obj_t *label = lv_label_create(button);
    lv_label_set_text(label, text);
    lv_obj_set_style_text_color(label, color(0x9AA8BD), 0);
    lv_obj_align(label, LV_ALIGN_LEFT_MID, 8, 0);
    return button;
}

static lv_obj_t *make_page(lv_obj_t *screen)
{
    lv_obj_t *page = lv_obj_create(screen);
    lv_obj_set_size(page, WINDOW_WIDTH - 210, WINDOW_HEIGHT - 80);
    lv_obj_set_pos(page, 210, 80);
    style_panel(page, 0x0A1020);
    lv_obj_set_style_radius(page, 0, 0);
    return page;
}

static void create_dashboard(void)
{
    lv_obj_t *screen = lv_screen_active();
    lv_obj_set_style_bg_color(screen, color(0x0A1020), 0);
    lv_obj_set_style_bg_opa(screen, LV_OPA_COVER, 0);
    lv_obj_set_scrollable(screen, false);

    lv_obj_t *header = lv_obj_create(screen);
    lv_obj_set_size(header, WINDOW_WIDTH, 68);
    lv_obj_set_pos(header, 0, 0);
    style_panel(header, 0x101A2D);
    lv_obj_set_style_radius(header, 0, 0);

    lv_obj_t *logo = make_panel(header, 24, 18, 32, 32, 0x51D6B2);
    lv_obj_set_style_radius(logo, 10, 0);
    make_label(header, "A", 35, 24, 0x0A1020);
    make_label(header, "ANTELOPE", 70, 17, 0xF1F5FC);
    make_label(header, "C BUILD WORKBENCH  /  POWERED BY LVGL 9.6", 70, 39, 0x8D9BB2);

    lv_obj_t *status = lv_obj_create(header);
    lv_obj_set_size(status, 122, 32);
    lv_obj_align(status, LV_ALIGN_RIGHT_MID, -22, 0);
    style_panel(status, 0x18352F);
    lv_obj_set_style_radius(status, 16, 0);
    make_label(status, "LIVE", 25, 8, 0x71E0BB);

    lv_obj_t *sidebar = lv_obj_create(screen);
    lv_obj_set_size(sidebar, 196, WINDOW_HEIGHT - 68);
    lv_obj_set_pos(sidebar, 0, 68);
    style_panel(sidebar, 0x0E1728);
    lv_obj_set_style_radius(sidebar, 0, 0);

    make_label(sidebar, "WORKSPACE", 22, 24, 0x687891);
    nav_buttons[0] = make_nav_button(sidebar, "Overview", 57, 0);
    nav_buttons[1] = make_nav_button(sidebar, "Performance", 107, 1);
    nav_buttons[2] = make_nav_button(sidebar, "Components", 157, 2);

    lv_obj_t *bottom_card = make_panel(sidebar, 14, 492, 164, 92, 0x141F32);
    make_label(bottom_card, "ANTELOPE STATUS", 14, 14, 0x8290A7);
    make_label(bottom_card, "Build plan ready", 14, 40, 0xE6EDF8);
    lv_obj_t *ready_dot = lv_obj_create(bottom_card);
    lv_obj_set_size(ready_dot, 8, 8);
    lv_obj_set_pos(ready_dot, 14, 69);
    style_panel(ready_dot, 0x51D6B2);
    lv_obj_set_style_radius(ready_dot, LV_RADIUS_CIRCLE, 0);
    make_label(bottom_card, "ref / compile / link", 30, 65, 0x8492A8);

    pages[0] = make_page(screen);
    pages[1] = make_page(screen);
    pages[2] = make_page(screen);
    lv_obj_set_hidden(pages[1], true);
    lv_obj_set_hidden(pages[2], true);

    lv_obj_t *overview = pages[0];
    make_label(overview, "Build with Antelope", 16, 16, 0xF1F5FC);
    make_label(overview, "Describe sources and targets once. Antel resolves refs, compiles, and links.",
               16, 44, 0x8D9BB2);

    lv_obj_t *card1 = make_panel(overview, 16, 86, 252, 120, 0x131F32);
    make_label(card1, "CONFIGURATION", 18, 17, 0x8290A7);
    make_label(card1, "JSON-driven targets", 18, 45, 0xF1F5FC);
    make_label(card1, "sources / flags / outputs", 18, 82, 0x62D8B6);

    lv_obj_t *card2 = make_panel(overview, 284, 86, 252, 120, 0x131F32);
    make_label(card2, "DEPENDENCIES", 18, 17, 0x8290A7);
    make_label(card2, "Git refs + hooks", 18, 45, 0xF1F5FC);
    make_label(card2, "branch pin / before_build", 18, 82, 0x72A8FF);

    lv_obj_t *card3 = make_panel(overview, 552, 86, 292, 120, 0x131F32);
    make_label(card3, "BUILD FEEDBACK", 18, 17, 0x8290A7);
    runtime_label = make_label(card3, "16 ms", 18, 45, 0xF1F5FC);
    make_label(card3, "Illustrative link-stage timing", 18, 82, 0xA181D0);

    lv_obj_t *chart = make_panel(overview, 16, 226, 536, 326, 0x131F32);
    make_label(chart, "A declarative build pipeline", 20, 18, 0xF1F5FC);
    make_label(chart, "Illustrative target activity / live LVGL rendering", 20, 43, 0x8290A7);

    lv_obj_t *chart_area = lv_obj_create(chart);
    lv_obj_set_size(chart_area, 484, 194);
    lv_obj_set_pos(chart_area, 24, 94);
    style_panel(chart_area, 0x101A2B);
    lv_obj_set_style_radius(chart_area, 10, 0);

    const uint32_t bar_colors[] = {
        0x51D6B2, 0x56CBAF, 0x53BEB5, 0x6AADD0,
        0x6F9FED, 0x738BE7, 0x8A83DB, 0xA181D0
    };
    for (uint32_t i = 0; i < 8; i++) {
        activity_bars[i] = lv_obj_create(chart_area);
        lv_obj_set_size(activity_bars[i], 32, 36 + (int)i * 5);
        lv_obj_align(activity_bars[i], LV_ALIGN_BOTTOM_LEFT, 18 + (int)i * 56, 0);
        style_panel(activity_bars[i], bar_colors[i]);
        lv_obj_set_style_radius(activity_bars[i], 6, 0);
    }

    const char *time_labels[] = {"REFS", "PLAN", "COMPILE", "LINK"};
    for (uint32_t i = 0; i < 4; i++) {
        make_label(chart, time_labels[i], 38 + (int)i * 122, 300, 0x76849A);
    }

    lv_obj_t *control = make_panel(overview, 568, 226, 276, 326, 0x131F32);
    make_label(control, "Explore Antel", 20, 20, 0xF1F5FC);
    make_label(control, "Build commands stay composable.", 20, 50, 0x8290A7);
    make_label(control, "DEMO INTERACTIONS", 20, 82, 0x8290A7);
    click_count_label = make_label(control, "0", 20, 110, 0x51D6B2);

    lv_obj_t *button = lv_button_create(control);
    lv_obj_set_size(button, 236, 46);
    lv_obj_set_pos(button, 20, 158);
    lv_obj_set_style_bg_color(button, color(0x2A8F7A), LV_PART_MAIN);
    lv_obj_set_style_bg_color(button, color(0x35A88F), LV_PART_MAIN | LV_STATE_PRESSED);
    lv_obj_set_style_radius(button, 10, LV_PART_MAIN);
    lv_obj_add_event_cb(button, on_demo_button, LV_EVENT_CLICKED, NULL);
    lv_obj_t *button_label = lv_label_create(button);
    lv_label_set_text(button_label, "Run build step");
    lv_obj_center(button_label);

    make_label(control, "Monitor update rate", 20, 226, 0x8290A7);
    slider_value_label = make_label(control, "50%", 205, 226, 0x72A8FF);
    lv_obj_t *slider = lv_slider_create(control);
    lv_obj_set_size(slider, 236, 12);
    lv_obj_set_pos(slider, 20, 260);
    lv_slider_set_range(slider, 0, 100);
    lv_slider_set_value(slider, 50, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(slider, color(0x26344A), LV_PART_MAIN);
    lv_obj_set_style_bg_color(slider, color(0x72A8FF), LV_PART_INDICATOR);
    lv_obj_set_style_bg_color(slider, color(0xF1F5FC), LV_PART_KNOB);
    lv_obj_add_event_cb(slider, on_slider_changed, LV_EVENT_VALUE_CHANGED, NULL);

    lv_obj_t *performance = pages[1];
    make_label(performance, "Build performance", 16, 16, 0xF1F5FC);
    make_label(performance, "An illustrative live view of Antel's parallel compile and link stages.",
               16, 44, 0x8D9BB2);

    lv_obj_t *cpu_card = make_panel(performance, 16, 86, 398, 116, 0x131F32);
    make_label(cpu_card, "CPU UTILIZATION", 20, 17, 0x8290A7);
    cpu_value_label = make_label(cpu_card, "42%", 322, 15, 0x51D6B2);
    cpu_bar = lv_bar_create(cpu_card);
    lv_obj_set_size(cpu_bar, 354, 14);
    lv_obj_set_pos(cpu_bar, 20, 62);
    lv_bar_set_range(cpu_bar, 0, 100);
    lv_bar_set_value(cpu_bar, 42, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(cpu_bar, color(0x26344A), LV_PART_MAIN);
    lv_obj_set_style_bg_color(cpu_bar, color(0x51D6B2), LV_PART_INDICATOR);

    lv_obj_t *memory_card = make_panel(performance, 430, 86, 414, 116, 0x131F32);
    make_label(memory_card, "MEMORY PRESSURE", 20, 17, 0x8290A7);
    memory_value_label = make_label(memory_card, "68%", 338, 15, 0x72A8FF);
    memory_bar = lv_bar_create(memory_card);
    lv_obj_set_size(memory_bar, 370, 14);
    lv_obj_set_pos(memory_bar, 20, 62);
    lv_bar_set_range(memory_bar, 0, 100);
    lv_bar_set_value(memory_bar, 68, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(memory_bar, color(0x26344A), LV_PART_MAIN);
    lv_obj_set_style_bg_color(memory_bar, color(0x72A8FF), LV_PART_INDICATOR);

    lv_obj_t *history = make_panel(performance, 16, 222, 536, 330, 0x131F32);
    make_label(history, "Build-stage activity", 20, 17, 0xF1F5FC);
    make_label(history, "Illustrative CPU and memory / rolling samples", 20, 43, 0x8290A7);
    telemetry_chart = lv_chart_create(history);
    lv_obj_set_size(telemetry_chart, 488, 238);
    lv_obj_set_pos(telemetry_chart, 24, 78);
    lv_chart_set_type(telemetry_chart, LV_CHART_TYPE_LINE);
    lv_chart_set_point_count(telemetry_chart, 24);
    lv_chart_set_axis_range(telemetry_chart, LV_CHART_AXIS_PRIMARY_Y, 0, 100);
    lv_chart_set_div_line_count(telemetry_chart, 5, 6);
    lv_obj_set_style_bg_color(telemetry_chart, color(0x101A2B), LV_PART_MAIN);
    lv_obj_set_style_border_width(telemetry_chart, 0, LV_PART_MAIN);
    lv_obj_set_style_line_color(telemetry_chart, color(0x27364D), LV_PART_MAIN);
    cpu_series = lv_chart_add_series(
        telemetry_chart,
        color(0x51D6B2),
        LV_CHART_AXIS_PRIMARY_Y
    );
    memory_series = lv_chart_add_series(
        telemetry_chart,
        color(0x72A8FF),
        LV_CHART_AXIS_PRIMARY_Y
    );
    lv_chart_set_all_values(telemetry_chart, cpu_series, 42);
    lv_chart_set_all_values(telemetry_chart, memory_series, 68);
    lv_chart_refresh(telemetry_chart);

    lv_obj_t *health = make_panel(performance, 568, 222, 276, 330, 0x131F32);
    make_label(health, "Antel capabilities", 20, 18, 0xF1F5FC);
    make_label(health, "TARGET TYPES", 20, 63, 0x8290A7);
    make_label(health, "static / shared / exe", 20, 88, 0x51D6B2);
    make_label(health, "REF WORKFLOW", 20, 137, 0x8290A7);
    make_label(health, "fetch branch-specific sources", 20, 162, 0x9AA8BD);
    make_label(health, "BUILD TOOLING", 20, 211, 0x8290A7);
    make_label(health, "before_build / diagnostics", 20, 236, 0x72A8FF);
    make_label(health, "No CMake required", 20, 277, 0xA181D0);

    lv_obj_t *components = pages[2];
    make_label(components, "LVGL component gallery", 16, 16, 0xF1F5FC);
    make_label(components, "Live widgets, custom styling, charts, states and interaction.",
               16, 44, 0x8D9BB2);

    lv_obj_t *widget_card = make_panel(components, 16, 86, 398, 466, 0x131F32);
    make_label(widget_card, "Interactive controls", 20, 20, 0xF1F5FC);
    make_label(widget_card, "Switches and checkboxes update app state.", 20, 49, 0x8290A7);

    lv_obj_t *live_switch = lv_switch_create(widget_card);
    lv_obj_set_pos(live_switch, 20, 98);
    lv_obj_add_state(live_switch, LV_STATE_CHECKED);
    lv_obj_add_event_cb(live_switch, on_live_updates_changed, LV_EVENT_VALUE_CHANGED, NULL);
    make_label(widget_card, "Live telemetry", 84, 103, 0xE6EDF8);
    component_status_label = make_label(widget_card, "Telemetry is updating", 84, 130, 0x51D6B2);

    lv_obj_t *checkbox = lv_checkbox_create(widget_card);
    lv_checkbox_set_text(checkbox, "Enable compact data labels");
    lv_obj_set_pos(checkbox, 20, 190);
    lv_obj_add_state(checkbox, LV_STATE_CHECKED);
    make_label(widget_card, "Checkable LVGL control", 20, 240, 0x8290A7);

    lv_obj_t *component_slider = lv_slider_create(widget_card);
    lv_obj_set_size(component_slider, 350, 12);
    lv_obj_set_pos(component_slider, 20, 293);
    lv_slider_set_range(component_slider, 1, 10);
    lv_slider_set_value(component_slider, 6, LV_ANIM_OFF);
    lv_obj_set_style_bg_color(component_slider, color(0x26344A), LV_PART_MAIN);
    lv_obj_set_style_bg_color(component_slider, color(0xA181D0), LV_PART_INDICATOR);
    lv_obj_set_style_bg_color(component_slider, color(0xF1F5FC), LV_PART_KNOB);
    make_label(widget_card, "Density control", 20, 326, 0x8290A7);

    lv_obj_t *reset_button = lv_button_create(widget_card);
    lv_obj_set_size(reset_button, 350, 46);
    lv_obj_set_pos(reset_button, 20, 382);
    lv_obj_set_style_bg_color(reset_button, color(0x2A8F7A), LV_PART_MAIN);
    lv_obj_set_style_radius(reset_button, 10, LV_PART_MAIN);
    lv_obj_add_event_cb(reset_button, on_reset_clicked, LV_EVENT_CLICKED, NULL);
    lv_obj_t *reset_label = lv_label_create(reset_button);
    lv_label_set_text(reset_label, "Reset interaction counter");
    lv_obj_center(reset_label);

    lv_obj_t *palette_card = make_panel(components, 430, 86, 414, 466, 0x131F32);
    make_label(palette_card, "Design system", 20, 20, 0xF1F5FC);
    make_label(palette_card, "Surface, accent, status and data colors", 20, 49, 0x8290A7);

    const uint32_t palette[] = {
        0x51D6B2, 0x72A8FF, 0xA181D0, 0xF4B860,
        0xE16A78, 0x26344A, 0x131F32, 0x0A1020
    };
    const char *palette_names[] = {
        "Mint", "Blue", "Violet", "Amber",
        "Coral", "Border", "Panel", "Canvas"
    };
    for (uint32_t i = 0; i < 8; i++) {
        int x = 20 + (int)(i % 2) * 184;
        int y = 94 + (int)(i / 2) * 76;
        lv_obj_t *swatch = make_panel(palette_card, x, y, 40, 40, palette[i]);
        lv_obj_set_style_radius(swatch, 10, 0);
        make_label(palette_card, palette_names[i], x + 52, y + 11, 0xC4CEDD);
    }
    make_label(palette_card, "Reusable primitives", 20, 414, 0x8290A7);

    dashboard_timer = lv_timer_create(update_dashboard, 750, NULL);
    select_page(0);
}

static void flush_display(lv_display_t *display, const lv_area_t *area,
                          uint8_t *pixels)
{
    SDL_Rect rect = {
        .x = area->x1,
        .y = area->y1,
        .w = area->x2 - area->x1 + 1,
        .h = area->y2 - area->y1 + 1
    };
    int pitch = rect.w * (int)sizeof(uint16_t);
    SDL_UpdateTexture(display_texture, &rect, pixels, pitch);
    SDL_RenderClear(renderer);
    SDL_RenderCopy(renderer, display_texture, NULL, NULL);
    SDL_RenderPresent(renderer);
    lv_display_flush_ready(display);
}

static void read_mouse(lv_indev_t *indev, lv_indev_data_t *data)
{
    (void)indev;
    int x;
    int y;
    uint32_t buttons = SDL_GetMouseState(&x, &y);
    data->point.x = x;
    data->point.y = y;
    data->state = (buttons & SDL_BUTTON(SDL_BUTTON_LEFT))
                      ? LV_INDEV_STATE_PRESSED
                      : LV_INDEV_STATE_RELEASED;
}

static int run_application(void)
{
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_TIMER) != 0) {
        fprintf(stderr, "SDL initialization failed: %s\n", SDL_GetError());
        return 1;
    }

    SDL_Window *window = SDL_CreateWindow(
        "Antel x LVGL 9.6",
        SDL_WINDOWPOS_CENTERED,
        SDL_WINDOWPOS_CENTERED,
        WINDOW_WIDTH,
        WINDOW_HEIGHT,
        SDL_WINDOW_SHOWN
    );
    if (window == NULL) {
        fprintf(stderr, "SDL window creation failed: %s\n", SDL_GetError());
        SDL_Quit();
        return 1;
    }
    app_window = window;

    renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_ACCELERATED);
    if (renderer == NULL) {
        renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_SOFTWARE);
    }
    if (renderer == NULL) {
        fprintf(stderr, "SDL renderer creation failed: %s\n", SDL_GetError());
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }

    display_texture = SDL_CreateTexture(
        renderer,
        SDL_PIXELFORMAT_RGB565,
        SDL_TEXTUREACCESS_STREAMING,
        WINDOW_WIDTH,
        WINDOW_HEIGHT
    );
    if (display_texture == NULL) {
        fprintf(stderr, "SDL texture creation failed: %s\n", SDL_GetError());
        SDL_DestroyRenderer(renderer);
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }

    lv_init();
    lv_display_t *display = lv_display_create(WINDOW_WIDTH, WINDOW_HEIGHT);
    if (display == NULL) {
        fprintf(stderr, "LVGL display creation failed.\n");
        SDL_DestroyTexture(display_texture);
        SDL_DestroyRenderer(renderer);
        SDL_DestroyWindow(window);
        SDL_Quit();
        return 1;
    }

    static uint8_t draw_buffer[WINDOW_WIDTH * DRAW_BUFFER_LINES * sizeof(uint16_t)];
    lv_display_set_color_format(display, LV_COLOR_FORMAT_RGB565);
    lv_display_set_flush_cb(display, flush_display);
    lv_display_set_buffers(
        display,
        draw_buffer,
        NULL,
        sizeof(draw_buffer),
        LV_DISPLAY_RENDER_MODE_PARTIAL
    );

    lv_indev_t *mouse = lv_indev_create();
    lv_indev_set_type(mouse, LV_INDEV_TYPE_POINTER);
    lv_indev_set_read_cb(mouse, read_mouse);
    lv_indev_set_display(mouse, display);

    create_dashboard();

    uint64_t previous_tick = SDL_GetPerformanceCounter();
    const uint64_t frequency = SDL_GetPerformanceFrequency();
    int running = 1;
    while (running) {
        SDL_Event event;
        while (SDL_PollEvent(&event)) {
            if (event.type == SDL_QUIT
                || (event.type == SDL_KEYDOWN && event.key.keysym.sym == SDLK_ESCAPE)) {
                running = 0;
            }
        }

        uint64_t current_tick = SDL_GetPerformanceCounter();
        uint32_t elapsed_ms = (uint32_t)(
            (current_tick - previous_tick) * 1000 / frequency
        );
        if (elapsed_ms > 0) {
            lv_tick_inc(elapsed_ms);
            previous_tick = current_tick;
        }

        lv_timer_handler();
        SDL_Delay(5);
    }

    lv_display_delete(display);
    lv_deinit();
    SDL_DestroyTexture(display_texture);
    SDL_DestroyRenderer(renderer);
    SDL_DestroyWindow(window);
    SDL_Quit();
    return 0;
}

int main(void)
{
    return run_application();
}
