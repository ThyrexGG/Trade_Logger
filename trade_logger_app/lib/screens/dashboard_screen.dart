import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/chart_loader.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool _isLoading = true;
  List<Map<String, dynamic>> _accounts = [];
  String _selectedAccount = 'All Accounts';
  Map<String, dynamic> _analytics = {};
  DateTime _currentCalendarMonth = DateTime.now();

  @override
  void initState() {
    super.initState();
    _loadDashboardData();
  }

  Future<void> _loadDashboardData() async {
    setState(() => _isLoading = true);
    final accounts = await ApiService.getAccounts();
    final analytics = await ApiService.getAnalytics(account: _selectedAccount);
    
    if (mounted) {
      setState(() {
        _accounts = accounts;
        _analytics = analytics;
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        body: Center(
          child: ChartPulseLoader(message: 'FETCHING LIVE BROKER FEEDS...'),
        ),
      );
    }

    final metrics = _analytics['metrics'] ?? {};
    final curvePoints = List<Map<String, dynamic>>.from(_analytics['spline_curve'] ?? []);
    final calendarPnl = Map<String, dynamic>.from(_analytics['calendar_pnl'] ?? {});

    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AppTheme.cyanAccent.withOpacity(0.12),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: AppTheme.cyanAccent.withOpacity(0.4)),
              ),
              child: const Text(
                'TRADE LOGGER PRO',
                style: TextStyle(
                  color: AppTheme.cyanAccent,
                  fontWeight: FontWeight.w900,
                  fontSize: 12,
                  letterSpacing: 1.0,
                ),
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.sync, color: AppTheme.cyanAccent),
            tooltip: 'Sync Brokers',
            onPressed: () async {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Syncing brokers in background...')),
              );
              await ApiService.triggerSync();
              await _loadDashboardData();
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        color: AppTheme.cyanAccent,
        onRefresh: _loadDashboardData,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // 1. Multi-Account Switcher Bar
            _buildAccountSwitcher(),
            const SizedBox(height: 16),

            // 2. Metrics & KPI Grid
            _buildMetricsGrid(metrics),
            const SizedBox(height: 20),

            // 3. Monotonic Hermite Spline Neon Balance Curve
            _buildSplineCurveCard(curvePoints),
            const SizedBox(height: 20),

            // 4. Interactive Calendar PnL Heatmap
            _buildCalendarCard(calendarPnl),
            const SizedBox(height: 30),
          ],
        ),
      ),
    );
  }

  Widget _buildAccountSwitcher() {
    List<String> accountOptions = ['All Accounts'];
    for (var acc in _accounts) {
      final name = acc['name']?.toString() ?? '';
      if (name.isNotEmpty && !accountOptions.contains(name)) {
        accountOptions.add(name);
      }
    }

    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: AppTheme.surfaceDark,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: Row(
        children: accountOptions.map((acc) {
          final isSelected = acc == _selectedAccount;
          return Expanded(
            child: GestureDetector(
              onTap: () {
                setState(() => _selectedAccount = acc);
                _loadDashboardData();
              },
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 10),
                decoration: BoxDecoration(
                  color: isSelected ? AppTheme.cyanAccent.withOpacity(0.15) : Colors.transparent,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: isSelected ? AppTheme.cyanAccent.withOpacity(0.5) : Colors.transparent,
                  ),
                ),
                child: Text(
                  acc.toUpperCase(),
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.5,
                    color: isSelected ? AppTheme.cyanAccent : AppTheme.textMuted,
                  ),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildMetricsGrid(Map<String, dynamic> metrics) {
    final netProfit = (metrics['net_profit'] ?? 0.0).toDouble();
    final winRate = (metrics['win_rate'] ?? 0.0).toDouble();
    final profitFactor = (metrics['profit_factor'] ?? 0.0).toDouble();
    final totalTrades = (metrics['total_trades'] ?? 0).toInt();

    final isPositive = netProfit >= 0;

    return Row(
      children: [
        Expanded(
          child: _buildMetricCard(
            title: 'NET PROFIT',
            value: '${isPositive ? "+" : ""}\$${netProfit.toStringAsFixed(2)}',
            valueColor: isPositive ? AppTheme.cyanAccent : AppTheme.tvRed,
            subtitle: '${totalTrades} trades executed',
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _buildMetricCard(
            title: 'WIN RATE',
            value: '${winRate.toStringAsFixed(1)}%',
            valueColor: winRate >= 50 ? AppTheme.neonLime : AppTheme.goldAccent,
            subtitle: 'Profit Factor: ${profitFactor}',
          ),
        ),
      ],
    );
  }

  Widget _buildMetricCard({
    required String title,
    required String value,
    required Color valueColor,
    required String subtitle,
  }) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.cardDark,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(
              fontSize: 10.5,
              fontWeight: FontWeight.w800,
              color: AppTheme.textMuted,
              letterSpacing: 0.8,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w900,
              color: valueColor,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            subtitle,
            style: const TextStyle(
              fontSize: 11,
              color: AppTheme.textDim,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSplineCurveCard(List<Map<String, dynamic>> points) {
    List<FlSpot> spots = [];
    double minBal = 10000.0;
    double maxBal = 10000.0;

    if (points.isNotEmpty) {
      for (int i = 0; i < points.length; i++) {
        final bal = (points[i]['balance'] ?? 10000.0).toDouble();
        if (bal < minBal) minBal = bal;
        if (bal > maxBal) maxBal = bal;
        spots.add(FlSpot(i.toDouble(), bal));
      }
    } else {
      spots = [const FlSpot(0, 10000), const FlSpot(1, 10000)];
    }

    final double yPadding = (maxBal - minBal) * 0.15;
    final double minY = (minBal - (yPadding > 50 ? yPadding : 100)).floorToDouble();
    final double maxY = (maxBal + (yPadding > 50 ? yPadding : 100)).ceilToDouble();

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.cardDark,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'EQUITY GROWTH CURVE (HERMITE SPLINE)',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textWhite,
                  letterSpacing: 0.6,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: AppTheme.neonLime.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Text(
                  '120 FPS NEON',
                  style: TextStyle(
                    fontSize: 9.5,
                    fontWeight: FontWeight.w900,
                    color: AppTheme.neonLime,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 220,
            child: LineChart(
              LineChartData(
                minY: minY,
                maxY: maxY,
                gridData: FlGridData(
                  show: true,
                  drawVerticalLine: false,
                  getDrawingHorizontalLine: (value) => FlLine(
                    color: Colors.white.withOpacity(0.04),
                    strokeWidth: 1,
                  ),
                ),
                titlesData: FlTitlesData(
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 52,
                      getTitlesWidget: (value, meta) {
                        return Text(
                          '\$${value.toInt()}',
                          style: const TextStyle(color: AppTheme.textDim, fontSize: 10),
                        );
                      },
                    ),
                  ),
                  bottomTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                ),
                borderData: FlBorderData(show: false),
                lineBarsData: [
                  LineChartBarData(
                    spots: spots,
                    isCurved: true,
                    curveSmoothness: 0.35,
                    color: AppTheme.neonLime,
                    barWidth: 2.8,
                    isStrokeCapRound: true,
                    dotData: FlDotData(
                      show: true,
                      getDotPainter: (spot, percent, barData, index) {
                        return FlDotCirclePainter(
                          radius: 3.5,
                          color: AppTheme.neonLime,
                          strokeWidth: 1.5,
                          strokeColor: Colors.black,
                        );
                      },
                    ),
                    belowBarData: BarAreaData(
                      show: true,
                      gradient: LinearGradient(
                        colors: [
                          AppTheme.neonLime.withOpacity(0.25),
                          AppTheme.neonLime.withOpacity(0.0),
                        ],
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCalendarCard(Map<String, dynamic> calendarPnl) {
    final monthFormat = DateFormat('MMMM yyyy');
    final daysInMonth = DateUtils.getDaysInMonth(_currentCalendarMonth.year, _currentCalendarMonth.month);
    final firstDayOfMonth = DateTime(_currentCalendarMonth.year, _currentCalendarMonth.month, 1);
    final int firstWeekday = firstDayOfMonth.weekday % 7; // Sunday = 0

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.cardDark,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.cardBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                monthFormat.format(_currentCalendarMonth).toUpperCase(),
                style: const TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w900,
                  color: AppTheme.cyanAccent,
                  letterSpacing: 0.8,
                ),
              ),
              Row(
                children: [
                  IconButton(
                    icon: const Icon(Icons.chevron_left, color: AppTheme.textMuted, size: 20),
                    onPressed: () {
                      setState(() {
                        _currentCalendarMonth = DateTime(
                          _currentCalendarMonth.year,
                          _currentCalendarMonth.month - 1,
                        );
                      });
                    },
                  ),
                  IconButton(
                    icon: const Icon(Icons.chevron_right, color: AppTheme.textMuted, size: 20),
                    onPressed: () {
                      setState(() {
                        _currentCalendarMonth = DateTime(
                          _currentCalendarMonth.year,
                          _currentCalendarMonth.month + 1,
                        );
                      });
                    },
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Weekday headers
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'].map((d) {
              return Text(
                d,
                style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: AppTheme.textDim),
              );
            }).toList(),
          ),
          const SizedBox(height: 8),

          // Days Grid
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 7,
              crossAxisSpacing: 6,
              mainAxisSpacing: 6,
              childAspectRatio: 0.95,
            ),
            itemCount: firstWeekday + daysInMonth,
            itemBuilder: (context, index) {
              if (index < firstWeekday) {
                return const SizedBox.shrink();
              }
              final dayNum = index - firstWeekday + 1;
              final dayDate = DateTime(_currentCalendarMonth.year, _currentCalendarMonth.month, dayNum);
              final dateKey = DateFormat('yyyy-MM-dd').format(dayDate);
              
              final dayData = calendarPnl[dateKey];
              final double pnl = (dayData != null ? dayData['pnl'] ?? 0.0 : 0.0).toDouble();
              final int trades = (dayData != null ? dayData['trades_count'] ?? 0 : 0).toInt();

              Color cellBg = Colors.white.withOpacity(0.03);
              Color pnlColor = AppTheme.textDim;
              if (trades > 0) {
                if (pnl > 0) {
                  cellBg = AppTheme.cyanAccent.withOpacity(0.18);
                  pnlColor = AppTheme.cyanAccent;
                } else if (pnl < 0) {
                  cellBg = AppTheme.tvRed.withOpacity(0.18);
                  pnlColor = AppTheme.tvRed;
                }
              }

              return Container(
                decoration: BoxDecoration(
                  color: cellBg,
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(
                    color: trades > 0 ? pnlColor.withOpacity(0.4) : Colors.transparent,
                  ),
                ),
                padding: const EdgeInsets.all(4),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      '$dayNum',
                      style: TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                        color: trades > 0 ? AppTheme.textWhite : AppTheme.textDim,
                      ),
                    ),
                    if (trades > 0) ...[
                      const SizedBox(height: 2),
                      Text(
                        '${pnl >= 0 ? "+" : ""}\$${pnl.toInt()}',
                        style: TextStyle(
                          fontSize: 8.5,
                          fontWeight: FontWeight.w900,
                          color: pnlColor,
                        ),
                      ),
                    ],
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }
}
