import 'package:flutter/material.dart';
import 'theme/app_theme.dart';
import 'screens/dashboard_screen.dart';
import 'screens/symbol_search_screen.dart';
import 'screens/trade_journal_screen.dart';
import 'screens/alerts_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const TradeLoggerApp());
}

class TradeLoggerApp extends StatelessWidget {
  const TradeLoggerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Trade Logger Pro',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: const MainNavigationShell(),
    );
  }
}

class MainNavigationShell extends StatefulWidget {
  const MainNavigationShell({Key? key}) : super(key: key);

  @override
  State<MainNavigationShell> createState() => _MainNavigationShellState();
}

class _MainNavigationShellState extends State<MainNavigationShell> {
  int _currentIndex = 0;

  final List<Widget> _screens = const [
    DashboardScreen(),
    SymbolSearchScreen(),
    TradeJournalScreen(),
    AlertsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _screens,
      ),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: AppTheme.surfaceDark,
          border: Border(top: BorderSide(color: AppTheme.cardBorder, width: 1)),
        ),
        child: NavigationBar(
          backgroundColor: AppTheme.surfaceDark,
          selectedIndex: _currentIndex,
          indicatorColor: AppTheme.cyanAccent.withOpacity(0.2),
          onDestinationSelected: (idx) => setState(() => _currentIndex = idx),
          destinations: const [
            NavigationDestination(
              icon: Icon(Icons.show_chart_rounded, color: AppTheme.textMuted),
              selectedIcon: Icon(Icons.show_chart_rounded, color: AppTheme.cyanAccent),
              label: 'Dashboard',
            ),
            NavigationDestination(
              icon: Icon(Icons.search_rounded, color: AppTheme.textMuted),
              selectedIcon: Icon(Icons.search_rounded, color: AppTheme.cyanAccent),
              label: 'Watchlist',
            ),
            NavigationDestination(
              icon: Icon(Icons.auto_stories_rounded, color: AppTheme.textMuted),
              selectedIcon: Icon(Icons.auto_stories_rounded, color: AppTheme.cyanAccent),
              label: 'Journal',
            ),
            NavigationDestination(
              icon: Icon(Icons.notifications_active_rounded, color: AppTheme.textMuted),
              selectedIcon: Icon(Icons.notifications_active_rounded, color: AppTheme.cyanAccent),
              label: 'Alerts',
            ),
          ],
        ),
      ),
    );
  }
}
