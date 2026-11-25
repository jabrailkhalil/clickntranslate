package dev.clickn.qa.page;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.view.WindowManager;
import android.widget.TextView;

public final class PageActivity extends Activity {
    private TextView card;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN | WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        card = new TextView(this);
        card.setGravity(Gravity.CENTER);
        card.setTextSize(48);
        card.setTextColor(Color.BLACK);
        card.setBackgroundColor(Color.WHITE);
        card.setOnLongClickListener(view -> {
            finishAndRemoveTask();
            return true;
        });
        setContentView(card);
        render(getIntent());
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        render(intent);
    }

    private void render(Intent intent) {
        card.setText("green".equals(intent.getStringExtra("page")) ? "Green door" : "Blue door");
    }
}
