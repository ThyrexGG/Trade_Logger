import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'http://127.0.0.1:8000/api';

  // 1. Accounts Summary
  static Future<List<Map<String, dynamic>>> getAccounts() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/accounts'));
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return List<Map<String, dynamic>>.from(data['accounts'] ?? []);
      }
    } catch (e) {
      print('Error fetching accounts: $e');
    }
    return [];
  }

  // 2. Trades History & Journal
  static Future<List<Map<String, dynamic>>> getTrades({String? account}) async {
    try {
      String url = '$baseUrl/trades?limit=150';
      if (account != null && account != 'All Accounts') {
        url += '&account=${Uri.encodeComponent(account)}';
      }
      final response = await http.get(Uri.parse(url));
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return List<Map<String, dynamic>>.from(data['trades'] ?? []);
      }
    } catch (e) {
      print('Error fetching trades: $e');
    }
    return [];
  }

  // 3. Analytics & Hermite Spline Curve
  static Future<Map<String, dynamic>> getAnalytics({String? account}) async {
    try {
      String url = '$baseUrl/analytics';
      if (account != null && account != 'All Accounts') {
        url += '?account=${Uri.encodeComponent(account)}';
      }
      final response = await http.get(Uri.parse(url));
      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
    } catch (e) {
      print('Error fetching analytics: $e');
    }
    return {};
  }

  // 4. TradingView Symbols Watchlist & Favorites
  static Future<List<Map<String, dynamic>>> getSymbols() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/symbols'));
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return List<Map<String, dynamic>>.from(data['symbols'] ?? []);
      }
    } catch (e) {
      print('Error fetching symbols: $e');
    }
    return [];
  }

  // 5. Toggle Red Ribbon Favorite
  static Future<bool> toggleFavoriteSymbol(String symbol) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/symbols/toggle-favorite'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({'symbol': symbol}),
      );
      return response.statusCode == 200;
    } catch (e) {
      print('Error toggling favorite: $e');
      return false;
    }
  }

  // 6. Price Alerts
  static Future<List<Map<String, dynamic>>> getAlerts() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/alerts'));
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        return List<Map<String, dynamic>>.from(data['alerts'] ?? []);
      }
    } catch (e) {
      print('Error fetching alerts: $e');
    }
    return [];
  }

  static Future<bool> createAlert(String symbol, double targetPrice, String condition, String notes) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/alerts'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'symbol': symbol,
          'target_price': targetPrice,
          'condition': condition,
          'notes': notes,
        }),
      );
      return response.statusCode == 200;
    } catch (e) {
      print('Error creating alert: $e');
      return false;
    }
  }

  static Future<bool> deleteAlert(int alertId) async {
    try {
      final response = await http.delete(Uri.parse('$baseUrl/alerts/$alertId'));
      return response.statusCode == 200;
    } catch (e) {
      print('Error deleting alert: $e');
      return false;
    }
  }

  // 7. Update Trade Journal
  static Future<bool> updateJournal({
    required int tradeId,
    required String notes,
    required String strategy,
    required int rating,
    String? screenshot,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/journal/update'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'trade_id': tradeId,
          'setup_notes': notes,
          'setup_strategy': strategy,
          'setup_rating': rating,
          'setup_screenshot': screenshot ?? '',
        }),
      );
      return response.statusCode == 200;
    } catch (e) {
      print('Error updating journal: $e');
      return false;
    }
  }

  // 8. Trigger Background Sync
  static Future<bool> triggerSync() async {
    try {
      final response = await http.post(Uri.parse('$baseUrl/sync'));
      return response.statusCode == 200;
    } catch (e) {
      print('Error triggering sync: $e');
      return false;
    }
  }
}
