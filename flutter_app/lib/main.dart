import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:trade_logger_app/notification_service.dart';

const String dashboardUrl = "https://tradelogger-bfepaizstq8o8xwrj3sdj5.streamlit.app";

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // Initialize Native Android Push Notification Service
  try {
    await NotificationService().init();
  } catch (e) {
    debugPrint("Notification init error: $e");
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
      ..setBackgroundColor(const Color(0xFF0C0F16))
      ..addJavaScriptChannel(
        'TradeAlert',
        onMessageReceived: (JavaScriptMessage message) {
          try {
            final data = jsonDecode(message.message);
            NotificationService().showNotification(
              title: data['title']?.toString() ?? 'Trade Alert',
              body: data['body']?.toString() ?? 'Trade closed on account',
            );
          } catch (e) {
            NotificationService().showNotification(
              title: 'Trade Closed Alert',
              body: message.message,
            );
          }
        },
      )
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
        backgroundColor: const Color(0xFF0C0F16),
        body: SafeArea(
          child: Stack(
            children: [
              RefreshIndicator(
                color: const Color(0xFF00FFCC),
                backgroundColor: const Color(0xFF121620),
                onRefresh: () async {
                  await _controller.reload();
                },
                child: WebViewWidget(controller: _controller),
              ),
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
