package com.example.tradelogger

import android.app.Activity
import android.os.Bundle
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import com.example.tradelogger.theme.TradeLoggerTheme

// Swap this URL with your deployed Streamlit Cloud URL or your local PC IP address:
// - Streamlit Cloud example: "https://your-app-name.streamlit.app"
// - Emulator testing (points to host PC localhost): "http://10.0.2.2:8502"
// - Real phone local testing: "http://<YOUR_PC_IP_ADDRESS>:8502"
const val DASHBOARD_URL = "http://10.0.2.2:8502"

class MainActivity : ComponentActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    enableEdgeToEdge()
    setContent {
      TradeLoggerTheme {
        Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
          TradeLoggerWebView(
            url = DASHBOARD_URL,
            modifier = Modifier
              .fillMaxSize()
              .statusBarsPadding()
              .navigationBarsPadding()
          )
        }
      }
    }
  }
}

@Composable
fun TradeLoggerWebView(url: String, modifier: Modifier = Modifier) {
  var webViewInstance: WebView? by remember { mutableStateOf(null) }
  val activity = LocalContext.current as? Activity

  BackHandler(enabled = true) {
    val wv = webViewInstance
    if (wv != null && wv.canGoBack()) {
      wv.goBack()
    } else {
      activity?.finish()
    }
  }

  AndroidView(
    factory = { context ->
      WebView(context).apply {
        webViewClient = WebViewClient()
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.useWideViewPort = true
        settings.loadWithOverviewMode = true
        loadUrl(url)
        webViewInstance = this
      }
    },
    modifier = modifier,
    update = {
      webViewInstance = it
    }
  )
}
