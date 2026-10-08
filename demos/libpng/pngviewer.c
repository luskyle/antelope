#include <gtk/gtk.h>
#include <png.h>
#include <math.h>
#include <string.h>

typedef struct {
    GtkWidget *window;
    GtkWidget *canvas;
    GtkWidget *scroll;
    GtkWidget *status;
    GdkPixbuf *pixels;
    char *filename;
    double scale;
    gboolean fit;
    gboolean smoke;
    gboolean painted;
} Viewer;

static void update_layout(Viewer *viewer)
{
    if (!viewer->pixels)
        return;
    int width = gdk_pixbuf_get_width(viewer->pixels);
    int height = gdk_pixbuf_get_height(viewer->pixels);
    if (viewer->fit) {
        GtkAllocation allocation;
        gtk_widget_get_allocation(viewer->scroll, &allocation);
        viewer->scale = MIN((allocation.width - 24.0) / width,
                            (allocation.height - 24.0) / height);
        viewer->scale = MAX(0.01, MIN(viewer->scale, 16.0));
    }
    gtk_widget_set_size_request(viewer->canvas,
                               (int)ceil(width * viewer->scale),
                               (int)ceil(height * viewer->scale));
    char *basename = g_path_get_basename(viewer->filename);
    char *status = g_strdup_printf("%s    %d x %d    %.0f%%    libpng %s",
                                  basename, width, height, viewer->scale * 100,
                                  png_get_libpng_ver(NULL));
    gtk_label_set_text(GTK_LABEL(viewer->status), status);
    g_free(status);
    g_free(basename);
    gtk_widget_queue_draw(viewer->canvas);
}

static gboolean load_png(Viewer *viewer, const char *filename)
{
    png_image image;
    memset(&image, 0, sizeof(image));
    image.version = PNG_IMAGE_VERSION;
    guchar *buffer = NULL;
    if (!png_image_begin_read_from_file(&image, filename))
        goto failed;
    image.format = PNG_FORMAT_RGBA;
    if (image.width > 16384 || image.height > 16384 ||
        PNG_IMAGE_SIZE(image) > 256 * 1024 * 1024) {
        g_strlcpy(image.message, "Image exceeds the 256 MiB / 16384 pixel limit",
                  sizeof(image.message));
        goto failed;
    }
    buffer = g_try_malloc(PNG_IMAGE_SIZE(image));
    if (!buffer) {
        g_strlcpy(image.message, "Not enough memory", sizeof(image.message));
        goto failed;
    }
    if (!png_image_finish_read(&image, NULL, buffer, 0, NULL))
        goto failed;
    GBytes *bytes = g_bytes_new_take(buffer, PNG_IMAGE_SIZE(image));
    GdkPixbuf *pixels = gdk_pixbuf_new_from_bytes(bytes, GDK_COLORSPACE_RGB,
                                                TRUE, 8, image.width,
                                                image.height, image.width * 4);
    g_bytes_unref(bytes);
    png_image_free(&image);
    g_clear_object(&viewer->pixels);
    viewer->pixels = pixels;
    g_free(viewer->filename);
    viewer->filename = g_strdup(filename);
    update_layout(viewer);
    return TRUE;

failed:
    g_printerr("PNG read failed: %s: %s\n", filename, image.message);
    if (!viewer->smoke) {
        GtkWidget *dialog = gtk_message_dialog_new(GTK_WINDOW(viewer->window),
            GTK_DIALOG_MODAL, GTK_MESSAGE_ERROR, GTK_BUTTONS_CLOSE,
            "Cannot open PNG");
        gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(dialog),
                                                  "%s\n%s", filename, image.message);
        gtk_dialog_run(GTK_DIALOG(dialog));
        gtk_widget_destroy(dialog);
    }
    g_free(buffer);
    png_image_free(&image);
    return FALSE;
}

static gboolean draw_image(GtkWidget *widget, cairo_t *context, gpointer data)
{
    Viewer *viewer = data;
    if (!viewer->pixels)
        return FALSE;
    double width = gdk_pixbuf_get_width(viewer->pixels) * viewer->scale;
    double height = gdk_pixbuf_get_height(viewer->pixels) * viewer->scale;
    double offset_x = MAX(0, (gtk_widget_get_allocated_width(widget) - width) / 2);
    double offset_y = MAX(0, (gtk_widget_get_allocated_height(widget) - height) / 2);
    cairo_translate(context, offset_x, offset_y);
    cairo_rectangle(context, 0, 0, width, height);
    cairo_clip(context);
    for (int row = 0; row < (int)ceil(height / 16); row++) {
        for (int column = 0; column < (int)ceil(width / 16); column++) {
            double shade = (row + column) % 2 ? 0.80 : 0.94;
            cairo_set_source_rgb(context, shade, shade, shade);
            cairo_rectangle(context, column * 16, row * 16, 16, 16);
            cairo_fill(context);
        }
    }
    cairo_scale(context, viewer->scale, viewer->scale);
    gdk_cairo_set_source_pixbuf(context, viewer->pixels, 0, 0);
    cairo_paint(context);
    viewer->painted = TRUE;
    return FALSE;
}

static void open_file(GtkButton *button, gpointer data)
{
    (void)button;
    Viewer *viewer = data;
    GtkWidget *dialog = gtk_file_chooser_dialog_new("Open PNG",
        GTK_WINDOW(viewer->window), GTK_FILE_CHOOSER_ACTION_OPEN,
        "Cancel", GTK_RESPONSE_CANCEL, "Open", GTK_RESPONSE_ACCEPT, NULL);
    GtkFileFilter *filter = gtk_file_filter_new();
    gtk_file_filter_set_name(filter, "PNG images");
    gtk_file_filter_add_mime_type(filter, "image/png");
    gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(dialog), filter);
    if (gtk_dialog_run(GTK_DIALOG(dialog)) == GTK_RESPONSE_ACCEPT) {
        char *filename = gtk_file_chooser_get_filename(GTK_FILE_CHOOSER(dialog));
        load_png(viewer, filename);
        g_free(filename);
    }
    gtk_widget_destroy(dialog);
}

static void change_zoom(GtkButton *button, gpointer data)
{
    Viewer *viewer = data;
    const char *action = gtk_widget_get_name(GTK_WIDGET(button));
    viewer->fit = strcmp(action, "fit") == 0;
    if (!viewer->fit)
        viewer->scale = CLAMP(viewer->scale *
                             (strcmp(action, "in") == 0 ? 1.25 : 0.8), 0.01, 16.0);
    update_layout(viewer);
}

static void resized(GtkWidget *widget, GtkAllocation *allocation, gpointer data)
{
    (void)widget;
    (void)allocation;
    Viewer *viewer = data;
    if (viewer->fit)
        update_layout(viewer);
}

static void add_button(GtkWidget *toolbar, const char *icon, const char *tooltip,
                       const char *name, GCallback callback, Viewer *viewer)
{
    GtkWidget *button = gtk_button_new_from_icon_name(icon, GTK_ICON_SIZE_BUTTON);
    gtk_widget_set_tooltip_text(button, tooltip);
    gtk_widget_set_name(button, name);
    gtk_box_pack_start(GTK_BOX(toolbar), button, FALSE, FALSE, 0);
    g_signal_connect(button, "clicked", callback, viewer);
}

static gboolean finish_smoke(gpointer data)
{
    Viewer *viewer = data;
    if (viewer->painted) {
        GdkWindow *window = gtk_widget_get_window(viewer->window);
        GdkPixbuf *capture = gdk_pixbuf_get_from_window(window, 0, 0,
            gdk_window_get_width(window), gdk_window_get_height(window));
        if (capture) {
            gdk_pixbuf_save(capture, "/tmp/antel-pngviewer.png", "png", NULL, NULL);
            g_object_unref(capture);
        }
        g_print("Decoded %d x %d PNG and rendered window using libpng %s\n",
            gdk_pixbuf_get_width(viewer->pixels),
            gdk_pixbuf_get_height(viewer->pixels), png_get_libpng_ver(NULL));
    }
    gtk_main_quit();
    return G_SOURCE_REMOVE;
}

int main(int argc, char **argv)
{
    Viewer viewer = {0};
    viewer.scale = 1;
    viewer.fit = TRUE;
    viewer.smoke = argc > 1 && strcmp(argv[1], "--smoke-test") == 0;
    char *executable = g_find_program_in_path(argv[0]);
    char *directory = g_path_get_dirname(executable ? executable : argv[0]);
    g_free(executable);
    char *sample = g_build_filename(directory, "testdata", "antel-logo.png", NULL);
    if (!g_file_test(sample, G_FILE_TEST_IS_REGULAR)) {
        g_free(sample);
        sample = g_build_filename(directory, "..", "share", "pngviewer_pngviewer",
                                  "testdata", "antel-logo.png", NULL);
    }
    const char *filename = argc > (viewer.smoke ? 2 : 1)
                         ? argv[viewer.smoke ? 2 : 1] : sample;
    if (!gtk_init_check(NULL, NULL)) {
        g_printerr("A graphical display is required.\n");
        g_free(directory);
        g_free(sample);
        return 1;
    }
    viewer.window = gtk_window_new(GTK_WINDOW_TOPLEVEL);
    gtk_window_set_title(GTK_WINDOW(viewer.window), "Antel PNG Viewer");
    gtk_window_set_default_size(GTK_WINDOW(viewer.window), 900, 680);
    GtkWidget *layout = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    gtk_container_add(GTK_CONTAINER(viewer.window), layout);
    GtkWidget *toolbar = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 6);
    gtk_container_set_border_width(GTK_CONTAINER(toolbar), 8);
    gtk_box_pack_start(GTK_BOX(layout), toolbar, FALSE, FALSE, 0);
    add_button(toolbar, "document-open-symbolic", "Open PNG", "open", G_CALLBACK(open_file), &viewer);
    add_button(toolbar, "zoom-out-symbolic", "Zoom out", "out", G_CALLBACK(change_zoom), &viewer);
    add_button(toolbar, "zoom-in-symbolic", "Zoom in", "in", G_CALLBACK(change_zoom), &viewer);
    add_button(toolbar, "zoom-fit-best-symbolic", "Fit to window", "fit", G_CALLBACK(change_zoom), &viewer);
    viewer.scroll = gtk_scrolled_window_new(NULL, NULL);
    gtk_box_pack_start(GTK_BOX(layout), viewer.scroll, TRUE, TRUE, 0);
    viewer.canvas = gtk_drawing_area_new();
    gtk_container_add(GTK_CONTAINER(viewer.scroll), viewer.canvas);
    viewer.status = gtk_label_new(NULL);
    gtk_widget_set_margin_bottom(viewer.status, 8);
    gtk_box_pack_start(GTK_BOX(layout), viewer.status, FALSE, FALSE, 0);
    g_signal_connect(viewer.canvas, "draw", G_CALLBACK(draw_image), &viewer);
    g_signal_connect(viewer.scroll, "size-allocate", G_CALLBACK(resized), &viewer);
    g_signal_connect(viewer.window, "destroy", G_CALLBACK(gtk_main_quit), NULL);
    gtk_widget_show_all(viewer.window);
    gboolean loaded = load_png(&viewer, filename);
    g_free(sample);
    g_free(directory);
    if (!viewer.smoke || loaded) {
        if (viewer.smoke)
            g_timeout_add(500, finish_smoke, &viewer);
        gtk_main();
    }
    g_clear_object(&viewer.pixels);
    g_free(viewer.filename);
    return viewer.smoke && (!loaded || !viewer.painted) ? 1 : 0;
}