package org.oguzdows.fixture;

/** Inert no-permission RemoteViews fixture; only the system may send widget broadcasts. */
public final class FixtureWidgetProvider extends android.appwidget.AppWidgetProvider {
    @Override public void onUpdate(android.content.Context context, android.appwidget.AppWidgetManager manager, int[] ids) {
        for (int id : ids) {
            android.widget.RemoteViews view = new android.widget.RemoteViews(context.getPackageName(), R.layout.fixture_widget);
            view.setTextViewText(R.id.widget_text, "Widget hazır · gerçek RemoteViews");
            manager.updateAppWidget(id, view);
        }
    }
}
