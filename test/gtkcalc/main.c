#include <adwaita.h>

#include <stdlib.h>
#include <string.h>

/* 计算器状态：accumulator 为累计值，entry 是当前输入 */
typedef struct {
    GtkLabel *display;
    char entry[64];
    int entry_len;
    double accumulator;
    double current;
    char pending_op; /* '\0' 无，'+' '-' '*' '/' */
    int fresh;       /* 刚按过运算符或等号，下一个数字重新开始 */
} Calc;

static guint g_autoclose = 0;

static void set_display(Calc *calc)
{
    char text[96];

    if (calc->pending_op != 0) {
        snprintf(text, sizeof(text), "%g %c %s", calc->accumulator, calc->pending_op, calc->entry);
    } else {
        snprintf(text, sizeof(text), "%s", calc->entry);
    }
    gtk_label_set_text(calc->display, text);
}

static void calc_clear(Calc *calc)
{
    strcpy(calc->entry, "0");
    calc->entry_len = 1;
    calc->accumulator = 0.0;
    calc->current = 0.0;
    calc->pending_op = 0;
    calc->fresh = 1;
    set_display(calc);
}

static void calc_apply(Calc *calc)
{
    calc->current = g_ascii_strtod(calc->entry, NULL);

    switch (calc->pending_op) {
    case '+': calc->accumulator += calc->current; break;
    case '-': calc->accumulator -= calc->current; break;
    case '*': calc->accumulator *= calc->current; break;
    case '/':
        calc->accumulator = (calc->current != 0.0) ? calc->accumulator / calc->current : 0.0;
        break;
    default: calc->accumulator = calc->current; break;
    }

    calc->pending_op = 0;
}

static void on_digit(Calc *calc, char digit)
{
    if (calc->fresh) {
        calc->entry[0] = digit;
        calc->entry[1] = '\0';
        calc->entry_len = 1;
        calc->fresh = 0;
    } else if (calc->entry_len < (int)sizeof(calc->entry) - 1
               && !(calc->entry_len == 1 && calc->entry[0] == '0')) {
        calc->entry[calc->entry_len++] = digit;
        calc->entry[calc->entry_len] = '\0';
    }
    set_display(calc);
}

static void on_dot(Calc *calc)
{
    if (calc->fresh) {
        strcpy(calc->entry, "0.");
        calc->entry_len = 2;
        calc->fresh = 0;
    } else if (strchr(calc->entry, '.') == NULL && calc->entry_len < (int)sizeof(calc->entry) - 1) {
        calc->entry[calc->entry_len++] = '.';
        calc->entry[calc->entry_len] = '\0';
    }
    set_display(calc);
}

static void on_operator(Calc *calc, char op)
{
    calc->current = g_ascii_strtod(calc->entry, NULL);

    if (calc->pending_op != 0) {
        calc_apply(calc);
    } else {
        calc->accumulator = calc->current;
    }

    calc->pending_op = op;
    calc->fresh = 1;
    set_display(calc);
}

static void on_equals(Calc *calc)
{
    calc_apply(calc);
    snprintf(calc->entry, sizeof(calc->entry), "%g", calc->accumulator);
    calc->entry_len = (int)strlen(calc->entry);
    calc->fresh = 1;
    set_display(calc);
}

static void on_button(GtkButton *button, gpointer user_data)
{
    Calc *calc = user_data;
    const char *label = gtk_button_get_label(button);

    if (strcmp(label, "C") == 0) {
        calc_clear(calc);
    } else if (strcmp(label, "=") == 0) {
        on_equals(calc);
    } else if (strcmp(label, ".") == 0) {
        on_dot(calc);
    } else if (strchr("+-*/", label[0]) != NULL && label[1] == '\0') {
        on_operator(calc, label[0]);
    } else {
        on_digit(calc, label[0]);
    }
}

static GtkWidget *make_button(Calc *calc, GtkGrid *grid, const char *text,
                              int col, int row, int width)
{
    GtkWidget *button = gtk_button_new_with_label(text);

    gtk_widget_set_hexpand(button, TRUE);
    gtk_widget_set_vexpand(button, TRUE);

    if (strcmp(text, "=") == 0) {
        gtk_widget_add_css_class(button, "suggested-action");
    } else if (strcmp(text, "C") == 0) {
        gtk_widget_add_css_class(button, "destructive-action");
    }

    g_signal_connect(button, "clicked", G_CALLBACK(on_button), calc);
    gtk_grid_attach(grid, button, col, row, width, 1);

    return button;
}

static void on_activate(GApplication *app, gpointer user_data)
{
    Calc *calc = g_new0(Calc, 1);

    GtkWidget *window = adw_application_window_new(GTK_APPLICATION(app));
    gtk_window_set_title(GTK_WINDOW(window), "Antelope 计算器");
    gtk_window_set_default_size(GTK_WINDOW(window), 320, 420);
    /* AdwApplicationWindow 自带 AdwHeaderBar 标题栏，无需手动设置 */

    /* 主体：显示 + 按键区 */
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 6);
    gtk_widget_set_margin_top(box, 8);
    gtk_widget_set_margin_bottom(box, 8);
    gtk_widget_set_margin_start(box, 8);
    gtk_widget_set_margin_end(box, 8);

    /* 显示行：右对齐、大字号 */
    calc->display = GTK_LABEL(gtk_label_new("0"));
    gtk_label_set_xalign(calc->display, 1.0);
    PangoAttrList *attrs = pango_attr_list_new();
    pango_attr_list_insert(attrs, pango_attr_size_new(26 * PANGO_SCALE));
    gtk_label_set_attributes(calc->display, attrs);
    gtk_box_append(GTK_BOX(box), GTK_WIDGET(calc->display));

    calc_clear(calc);

    /* 按键区 5 行 x 4 列 */
    GtkWidget *grid = gtk_grid_new();
    gtk_widget_set_vexpand(grid, TRUE);
    gtk_grid_set_row_homogeneous(GTK_GRID(grid), TRUE);
    gtk_grid_set_column_homogeneous(GTK_GRID(grid), TRUE);
    gtk_grid_set_row_spacing(GTK_GRID(grid), 4);
    gtk_grid_set_column_spacing(GTK_GRID(grid), 4);

    make_button(calc, GTK_GRID(grid), "C", 0, 0, 1);
    make_button(calc, GTK_GRID(grid), "/", 1, 0, 1);
    make_button(calc, GTK_GRID(grid), "*", 2, 0, 1);
    make_button(calc, GTK_GRID(grid), "-", 3, 0, 1);

    make_button(calc, GTK_GRID(grid), "7", 0, 1, 1);
    make_button(calc, GTK_GRID(grid), "8", 1, 1, 1);
    make_button(calc, GTK_GRID(grid), "9", 2, 1, 1);
    make_button(calc, GTK_GRID(grid), "+", 3, 1, 1);

    make_button(calc, GTK_GRID(grid), "4", 0, 2, 1);
    make_button(calc, GTK_GRID(grid), "5", 1, 2, 1);
    make_button(calc, GTK_GRID(grid), "6", 2, 2, 1);
    make_button(calc, GTK_GRID(grid), "=", 3, 2, 1);

    make_button(calc, GTK_GRID(grid), "1", 0, 3, 1);
    make_button(calc, GTK_GRID(grid), "2", 1, 3, 1);
    make_button(calc, GTK_GRID(grid), "3", 2, 3, 1);
    make_button(calc, GTK_GRID(grid), "=", 3, 3, 1);

    make_button(calc, GTK_GRID(grid), "0", 0, 4, 2);
    make_button(calc, GTK_GRID(grid), ".", 2, 4, 1);
    make_button(calc, GTK_GRID(grid), "=", 3, 4, 1);

    gtk_box_append(GTK_BOX(box), grid);
    adw_application_window_set_content(ADW_APPLICATION_WINDOW(window), box);

    if (g_autoclose > 0) {
        g_timeout_add_seconds(g_autoclose, (GSourceFunc)gtk_window_destroy, window);
    }

    gtk_window_present(GTK_WINDOW(window));
}

int main(int argc, char **argv)
{
    /* GTK4 的 g_application_run 会解析并拒绝未知选项，先剥掉 --auto-close */
    int out_argc = 1;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--auto-close") == 0 && i + 1 < argc) {
            g_autoclose = (guint)atoi(argv[i + 1]);
            i++;
        } else {
            argv[out_argc++] = argv[i];
        }
    }
    argv[out_argc] = NULL;

    AdwApplication *app = adw_application_new("io.github.luskyle.antelcalc", G_APPLICATION_FLAGS_NONE);
    g_signal_connect(app, "activate", G_CALLBACK(on_activate), NULL);
    int status = g_application_run(G_APPLICATION(app), out_argc, argv);
    g_object_unref(app);

    return status;
}