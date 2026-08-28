import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:onesignal_flutter/onesignal_flutter.dart';

// Swap this URL with your deployed Streamlit Cloud URL or your local PC IP address:
// - Streamlit Cloud example: "https://your-app-name.streamlit.app"
// - Emulator testing (points to host PC localhost): "http://10.0.2.2:8502"
// - Real phone local testing: "http://<YOUR_PC_IP_ADDRESS>:8502"
const String dashboardUrl = "https://tradelogger-bfepaizstq8o8xwrj3sdj5.streamlit.app";
const String oneSignalAppId = "1f707b9d-5a8e-411d-b8cc-13c68a9b7ff4";

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // Initialize Native OneSignal Push Notifications
  try {
    OneSignal.initialize(oneSignalAppId);
    // Prompt user for push notification permissions
    OneSignal.Notifications.requestPermission(true);
  } catch (e) {
    debugPrint("OneSignal initialization error: $e");
  }

  runApp(const TradeLoggerApp());
}

class TradeLoggerApp extends StatelessWidget {
  const TradeLoggerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Trade Logger',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        primaryColor: const Color(0xFF00FFCC),
        scaffoldBackgroundColor: const Color(0xFF0C0F16),
      ),
      home: const DashboardWebViewPage(),
    );
  }
}

class DashboardWebViewPage extends StatefulWidget {
  const DashboardWebViewPage({super.key});

  @override
  State<DashboardWebViewPage> createState() => _DashboardWebViewPageState();
}

class _DashboardWebViewPageState extends State<DashboardWebViewPage> {
  late final WebViewController _controller;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageStarted: (String url) {
            setState(() {
              _isLoading = true;
            });
          },
          onPageFinished: (String url) {
            setState(() {
              _isLoading = false;
            });
          },
          onWebResourceError: (WebResourceError error) {
            debugPrint("WebView error: ${error.description}");
          },
        ),
      )
      ..loadRequest(Uri.parse(dashboardUrl));
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (bool didPop, dynamic result) async {
        if (didPop) return;
        if (await _controller.canGoBack()) {
          await _controller.goBack();
        } else {
          SystemNavigator.pop();
        }
      },
      child: Scaffold(
        body: SafeArea(
          child: Stack(
            children: [
              WebViewWidget(controller: _controller),
              if (_isLoading)
                const Center(
                  child: CircularProgressIndicator(
                    color: Color(0xFF00FFCC),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
