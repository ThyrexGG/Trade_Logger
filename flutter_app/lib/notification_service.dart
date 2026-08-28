import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:http/http.dart' as http;

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  final FlutterLocalNotificationsPlugin _notificationsPlugin = FlutterLocalNotificationsPlugin();
  Set<String> _knownTradeIds = {};
  Timer? _pollingTimer;

  Future<void> init() async {
    const AndroidInitializationSettings androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const InitializationSettings initSettings = InitializationSettings(android: androidSettings);

    await _notificationsPlugin.initialize(
      initSettings,
      onDidReceiveNotificationResponse: (NotificationResponse response) {
        debugPrint("Notification clicked: ${response.payload}");
      },
    );

    // Request Android 13+ Notification Permission
    await _notificationsPlugin
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
        ?.requestNotificationsPermission();

    // Start background trade check
    startTradeChecker();
  }

  Future<void> showNotification({required String title, required String body, String? payload}) async {
    const AndroidNotificationDetails androidDetails = AndroidNotificationDetails(
      'trade_alerts_channel',
      'Trade Alerts',
      channelDescription: 'Real-time trade close and risk limit notifications',
      importance: Importance.max,
      priority: Priority.high,
      showWhen: true,
      enableVibration: true,
      playSound: true,
    );

    const NotificationDetails platformDetails = NotificationDetails(android: androidDetails);

    await _notificationsPlugin.show(
      DateTime.now().millisecondsSinceEpoch ~/ 1000,
      title,
      body,
      platformDetails,
      payload: payload,
    );
  }

  void startTradeChecker() {
    _pollingTimer?.cancel();
    // Check every 30 seconds directly from cloud
    _pollingTimer = Timer.periodic(const Duration(seconds: 30), (timer) {
      _checkRecentTrades();
    });
  }

  Future<void> _checkRecentTrades() async {
    // Queries Supabase REST API for closed trades
    const String supabaseUrl = "https://wutzxzophrfkqpylcswc.supabase.co/rest/v1/closed_trades?select=*&order=exit_time.desc&limit=5";
    const String apiKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Ind1dHp4em9waHJma3FweWxjc3djIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjQ4MzIzMjUsImV4cCI6MjA0MDQwODMyNX0.u1jR-cZp91dJ8pE078g_Z5Gq17B6G4U01";

    try {
      final response = await http.get(
        Uri.parse(supabaseUrl),
        headers: {
          "apikey": apiKey,
          "Authorization": "Bearer $apiKey",
        },
      ).timeout(const Duration(seconds: 8));

      if (response.statusCode == 200) {
        final List<dynamic> trades = jsonDecode(response.body);
        if (_knownTradeIds.isEmpty) {
          // Initial population
          for (var t in trades) {
            _knownTradeIds.add(t['trade_id'].toString());
          }
        } else {
          for (var t in trades) {
            final tradeId = t['trade_id'].toString();
            if (!_knownTradeIds.contains(tradeId)) {
              _knownTradeIds.add(tradeId);
              final pnl = (t['net_profit'] as num?)?.toDouble() ?? 0.0;
              final pnlSign = pnl >= 0 ? "+" : "-";
              final sym = t['symbol']?.toString() ?? 'TRADE';
              final dir = t['direction']?.toString() ?? 'ORDER';
              
              showNotification(
                title: "Trade Closed: $sym ($pnlSign\$${pnl.abs().toStringAsFixed(2)})",
                body: "$dir • Net PnL: $pnlSign\$${pnl.abs().toStringAsFixed(2)}",
                payload: tradeId,
              );
            }
          }
        }
      }
    } catch (e) {
      debugPrint("Trade checker error: $e");
    }
  }
}
