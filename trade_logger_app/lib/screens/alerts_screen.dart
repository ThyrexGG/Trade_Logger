import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/chart_loader.dart';

class AlertsScreen extends StatefulWidget {
  const AlertsScreen({Key? key}) : super(key: key);

  @override
  State<AlertsScreen> createState() => _AlertsScreenState();
}

class _AlertsScreenState extends State<AlertsScreen> {
  bool _isLoading = true;
  List<Map<String, dynamic>> _alerts = [];

  @override
  void initState() {
    super.initState();
    _loadAlerts();
  }

  Future<void> _loadAlerts() async {
    setState(() => _isLoading = true);
    final alerts = await ApiService.getAlerts();
    if (mounted) {
      setState(() {
        _alerts = alerts;
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Active Price Alerts',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
        ),
      ),
      body: _isLoading
          ? const ChartPulseLoader(message: 'MONITORING PRICE TARGETS...')
          : _alerts.isEmpty
              ? const Center(
                  child: Text(
                    'No active price alerts.\nGo to Symbol Search to set an alert.',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: AppTheme.textDim),
                  ),
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _alerts.length,
                  itemBuilder: (context, index) {
                    final al = _alerts[index];
                    final String sym = al['symbol']?.toString() ?? 'ASSET';
                    final double target = (al['target_price'] ?? 0.0).toDouble();
                    final String cond = al['condition']?.toString() ?? 'ABOVE';
                    final String notes = al['notes']?.toString() ?? '';
                    final int alertId = (al['id'] ?? 0).toInt();

                    return Container(
                      margin: const EdgeInsets.only(bottom: 10),
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: AppTheme.cardDark,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: AppTheme.cyanAccent.withOpacity(0.25)),
                      ),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Text(
                                    sym,
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w800,
                                      fontSize: 14,
                                      color: Colors.white,
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: AppTheme.cyanAccent.withOpacity(0.12),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(
                                      cond == 'ABOVE' ? '>= CROSS' : '<= DROP',
                                      style: const TextStyle(
                                        fontSize: 9.5,
                                        fontWeight: FontWeight.w900,
                                        color: AppTheme.cyanAccent,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'Target: \$${target.toStringAsFixed(2)}',
                                style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: AppTheme.neonLime),
                              ),
                              if (notes.isNotEmpty) ...[
                                const SizedBox(height: 2),
                                Text(
                                  notes,
                                  style: const TextStyle(fontSize: 11, color: AppTheme.textDim),
                                ),
                              ],
                            ],
                          ),
                          IconButton(
                            icon: const Icon(Icons.delete_outline, color: AppTheme.tvRed, size: 20),
                            onPressed: () async {
                              await ApiService.deleteAlert(alertId);
                              _loadAlerts();
                            },
                          ),
                        ],
                      ),
                    );
                  },
                ),
    );
  }
}
