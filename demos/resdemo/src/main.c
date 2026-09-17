/* 资源打包窗体演示：一个程序同时用三种形态携带资源，界面由资源驱动。

   三种形态与界面中的对应关系：
   1. data_files —— 目录分发：assets/ 复制进输出目录，程序按 /proc/self/exe
      定位资源目录（与 cwd 无关），点「重新读取」可重读磁盘上的 banner.txt
   2. embed     —— 单文件分发：ld -r -b binary 嵌入的 payload.bin 经
      _binary_ 符号读出，界面展示字节数与校验和
   3. gresource —— 单文件分发：整个界面（main.ui）、样式（style.css）、
      图标（logo.png）全部编译进二进制，GtkBuilder / CSS provider 直接
      按资源路径加载；改资源 → antel build 重编 gresource 单元 → 换肤

   界面交互：深色/浅色切换（样式来自 gresource）+ 重读 data_files。
*/

#define _GNU_SOURCE
#include <adwaita.h>
#include <gio/gio.h>

#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* embed：assets/payload.bin → _binary_assets_payload_bin_start/_end（路径转下划线） */
extern const unsigned char _binary_assets_payload_bin_start[];
extern const unsigned char _binary_assets_payload_bin_end[];

typedef struct {
    GtkWidget *window;
    GtkLabel *data_content;
    GtkLabel *embed_content;
    GtkLabel *gres_content;
    GtkLabel *statusbar;
    GtkSwitch *dark_switch;
    char *exe_dir;
    guint autoclose;
} App;

static void set_status(App *app, const char *message)
{
    gtk_label_set_text(app->statusbar, message);
}

static char *exec_dir(void)
{
    char buf[PATH_MAX];
    ssize_t n = readlink("/proc/self/exe", buf, sizeof(buf) - 1);
    if (n < 0) {
        return strdup(".");
    }
    buf[n] = '\0';
    char *slash = strrchr(buf, '/');
    if (slash == NULL) {
        return strdup(".");
    }
    *slash = '\0';
    return strdup(buf[0] == '\0' ? "/" : buf);
}

static char *read_file(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (f == NULL) {
        return NULL;
    }
    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    rewind(f);
    char *data = malloc((size_t)len + 1);
    if (data != NULL) {
        size_t got = fread(data, 1, (size_t)len, f);
        data[got] = '\0';
    }
    fclose(f);
    return data;
}

static void refresh_data(App *app)
{
    char path[PATH_MAX];
    snprintf(path, sizeof(path), "%s/assets/banner.txt", app->exe_dir);
    char *banner = read_file(path);
    if (banner == NULL) {
        gtk_label_set_text(app->data_content, "banner.txt 未找到");
        set_status(app, "data_files: 未找到 assets/banner.txt");
    } else {
        gtk_label_set_text(app->data_content, banner);
        char status[PATH_MAX + 64];
        snprintf(status, sizeof(status), "data_files: 已重新读取 %s", path);
        set_status(app, status);
        free(banner);
    }
}

static void on_refresh(GtkButton *button, gpointer user_data)
{
    App *app = user_data;
    refresh_data(app);
    set_status(app, "data_files: 已从磁盘重新读取");
}

static void on_theme_toggle(GtkSwitch *sw, GParamSpec *pspec, gpointer user_data)
{
    App *app = user_data;
    gboolean dark = gtk_switch_get_active(sw);
    AdwStyleManager *manager = adw_style_manager_get_default();
    adw_style_manager_set_color_scheme(manager, dark ? ADW_COLOR_SCHEME_FORCE_DARK
                                                     : ADW_COLOR_SCHEME_FORCE_LIGHT);
    set_status(app, dark ? "主题: 深色（style.css 来自 gresource）"
                         : "主题: 浅色（style.css 来自 gresource）");
}

static void populate_embed(App *app)
{
    const unsigned char *start = _binary_assets_payload_bin_start;
    const unsigned char *end = _binary_assets_payload_bin_end;
    size_t len = (size_t)(end - start);
    unsigned char checksum = 0;
    size_t show = len < 8 ? len : 8;

    for (size_t i = 0; i < len; i++) {
        checksum = (unsigned char)(checksum + start[i]);
    }

    char text[256];
    int pos = snprintf(text, sizeof(text), "payload: %zu bytes\n校验和: 0x%02x\n前 %zu 字节: ",
                       len, checksum, show);
    for (size_t i = 0; i < show; i++) {
        pos += snprintf(text + pos, sizeof(text) - (size_t)pos, "%02x ", start[i]);
    }
    gtk_label_set_text(app->embed_content, text);
}

static void populate_gresource(App *app)
{
    GError *error = NULL;
    GBytes *bytes = g_resources_lookup_data("/com/antelope/demo/share/notes.txt",
                                            G_RESOURCE_LOOKUP_FLAGS_NONE, &error);
    if (bytes == NULL) {
        gtk_label_set_text(app->gres_content, error ? error->message : "lookup failed");
        if (error != NULL) {
            g_error_free(error);
        }
        return;
    }
    gsize size = 0;
    const char *data = g_bytes_get_data(bytes, &size);
    char text[512];
    snprintf(text, sizeof(text), "notes.txt (%zu bytes):\n%.*s", size, (int)size, data);
    gtk_label_set_text(app->gres_content, text);
    g_bytes_unref(bytes);
}

static void apply_theme(App *app, gboolean dark)
{
    AdwStyleManager *manager = adw_style_manager_get_default();
    adw_style_manager_set_color_scheme(manager, dark ? ADW_COLOR_SCHEME_FORCE_DARK
                                                     : ADW_COLOR_SCHEME_FORCE_LIGHT);
}

static void on_activate(GApplication *application, gpointer user_data)
{
    App *app = g_new0(App, 1);
    app->exe_dir = exec_dir();
    app->autoclose = (guint)GPOINTER_TO_INT(user_data);

    /* 窗口与顶层容器（libadwaita 1.1 的 AdwApplicationWindow 用其自己的 set_content） */
    GtkWidget *window = adw_application_window_new(GTK_APPLICATION(application));
    gtk_window_set_title(GTK_WINDOW(window), "Antelope 资源演示");
    gtk_window_set_default_size(GTK_WINDOW(window), 520, 720);
    app->window = window;

    /* 样式：直接按资源路径加载 CSS（改 style.css → antel build → 换肤） */
    GtkCssProvider *provider = gtk_css_provider_new();
    gtk_css_provider_load_from_resource(provider, "/com/antelope/demo/css/style.css");
    gtk_style_context_add_provider_for_display(gtk_widget_get_display(window),
                                               GTK_STYLE_PROVIDER(provider),
                                               GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);

    /* 界面：整个 main.ui 从 gresource 加载 */
    GtkBuilder *builder = gtk_builder_new_from_resource("/com/antelope/demo/ui/main.ui");
    GtkWidget *root = GTK_WIDGET(gtk_builder_get_object(builder, "root_box"));

    app->data_content = GTK_LABEL(gtk_builder_get_object(builder, "data_content"));
    app->embed_content = GTK_LABEL(gtk_builder_get_object(builder, "embed_content"));
    app->gres_content = GTK_LABEL(gtk_builder_get_object(builder, "gres_content"));
    app->statusbar = GTK_LABEL(gtk_builder_get_object(builder, "statusbar"));
    app->dark_switch = GTK_SWITCH(gtk_builder_get_object(builder, "dark_switch"));

    /* 图标：从 gresource 加载 logo.png */
    GtkImage *logo = GTK_IMAGE(gtk_builder_get_object(builder, "hero_logo"));
    gtk_image_set_from_resource(logo, "/com/antelope/demo/img/logo.png");

    GtkButton *refresh_btn = GTK_BUTTON(gtk_builder_get_object(builder, "refresh_btn"));
    g_signal_connect(refresh_btn, "clicked", G_CALLBACK(on_refresh), app);
    g_signal_connect(app->dark_switch, "notify::active", G_CALLBACK(on_theme_toggle), app);

    /* 注意：不释 builder——它持有的控件（包括 root 树）引用计数归零会一起销毁。
       窗口存续期间 builder 必须活着，这是 GTK 的常规做法 */

    adw_application_window_set_content(ADW_APPLICATION_WINDOW(window), root);

    /* 让初始颜色方案与开关一致 */
    apply_theme(app, gtk_switch_get_active(app->dark_switch));

    refresh_data(app);
    populate_embed(app);
    populate_gresource(app);
    set_status(app, "就绪：三种资源形态全部加载（改资源后 antel build 会增量更新）");

    if (app->autoclose > 0) {
        g_timeout_add_seconds(app->autoclose, (GSourceFunc)gtk_window_destroy, window);
    }

    gtk_window_present(GTK_WINDOW(window));
}

int main(int argc, char **argv)
{
    /* GTK4 的 g_application_run 会解析并拒绝未知选项，先剥掉 --auto-close */
    guint autoclose = 0;
    int out_argc = 1;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--auto-close") == 0 && i + 1 < argc) {
            autoclose = (guint)atoi(argv[i + 1]);
            i++;
        } else {
            argv[out_argc++] = argv[i];
        }
    }
    argv[out_argc] = NULL;

    /* 注册全部 libadwaita 类型：.ui 里的 AdwHeaderBar 等 GType 是惰性注册的，
       不先 adw_init() 的话 GtkBuilder 会报 "Invalid object type" */
    adw_init();

    AdwApplication *app = adw_application_new("io.github.luskyle.resdemo",
                                              G_APPLICATION_FLAGS_NONE);
    g_signal_connect(app, "activate", G_CALLBACK(on_activate),
                     GINT_TO_POINTER((gint)autoclose));
    int status = g_application_run(G_APPLICATION(app), out_argc, argv);
    g_object_unref(app);

    return status;
}