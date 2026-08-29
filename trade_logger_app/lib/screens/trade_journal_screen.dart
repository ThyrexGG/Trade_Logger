import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/chart_loader.dart';

class TradeJournalScreen extends StatefulWidget {
  const TradeJournalScreen({Key? key}) : super(key: key);

  @override
  State<TradeJournalScreen> createState() => _TradeJournalScreenState();
}

class _TradeJournalScreenState extends State<TradeJournalScreen> {
  bool _isLoading = true;
  List<Map<String, dynamic>> _trades = [];
  String _selectedAccountTab = 'All Accounts';

  @override
  void initState() {
    super.initState();
    _loadTrades();
  }

  Future<void> _loadTrades() async {
    setState(() => _isLoading = true);
    final trades = await ApiService.getTrades(account: _selectedAccountTab);
    if (mounted) {
      setState(() {
        _trades = trades;
        _isLoading = false;
      });
    }
  }

  void _openTradeStudio(Map<String, dynamic> trade) {
    final int tradeId = (trade['id'] ?? trade['ticket'] ?? 0).toInt();
    final TextEditingController notesCtrl = TextEditingController(text: trade['setup_notes']?.toString() ?? '');
    final TextEditingController screenshotCtrl = TextEditingController(text: trade['setup_screenshot']?.toString() ?? '');
    String selectedStrategy = trade['setup_strategy']?.toString() ?? 'Breakout';
    int rating = (trade['setup_rating'] ?? 5).toInt();

    final strategies = ['Breakout', 'Order Block', 'Liquidity Sweep', 'Trend Following', 'Range Bounce'];

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppTheme.surfaceDark,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setModalState) {
            return Padding(
              padding: EdgeInsets.only(
                left: 16,
                right: 16,
                top: 20,
                bottom: MediaQuery.of(ctx).viewInsets.bottom + 20,
              ),
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          'TRADE SETUP #${tradeId} - ${trade['symbol']}',
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w900,
                            color: AppTheme.cyanAccent,
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.close, color: AppTheme.textMuted, size: 20),
                          onPressed: () => Navigator.pop(ctx),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),

                    // Strategy Tag Selector
                    const Text('Setup Strategy Tag', style: TextStyle(fontSize: 11, color: AppTheme.textMuted)),
                    const SizedBox(height: 6),
                    Wrap(
                      spacing: 6,
                      children: strategies.map((st) {
                        final isSel = selectedStrategy == st;
                        return ChoiceChip(
                          label: Text(st, style: TextStyle(fontSize: 11, color: isSel ? Colors.black : Colors.white)),
                          selected: isSel,
                          selectedColor: AppTheme.cyanAccent,
                          backgroundColor: AppTheme.cardDark,
                          onSelected: (val) => setModalState(() => selectedStrategy = st),
                        );
                      }).toList(),
                    ),
                    const SizedBox(height: 14),

                    // Screenshot URL / Image Preview
                    const Text('Chart Screenshot (URL or Image Link)', style: TextStyle(fontSize: 11, color: AppTheme.textMuted)),
                    const SizedBox(height: 4),
                    TextField(
                      controller: screenshotCtrl,
                      style: const TextStyle(color: Colors.white, fontSize: 12),
                      decoration: InputDecoration(
                        hintText: 'https://... or chart image link',
                        hintStyle: const TextStyle(color: AppTheme.textDim, fontSize: 12),
                        filled: true,
                        fillColor: AppTheme.cardDark,
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                      ),
                      onChanged: (val) => setModalState(() {}),
                    ),
                    if (screenshotCtrl.text.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: Image.network(
                          screenshotCtrl.text,
                          height: 140,
                          width: double.infinity,
                          fit: BoxFit.cover,
                          errorBuilder: (ctx, err, stack) => Container(
                            height: 60,
                            color: AppTheme.cardDark,
                            alignment: Alignment.center,
                            child: const Text('Invalid image link', style: TextStyle(fontSize: 11, color: AppTheme.textDim)),
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: 14),

                    // Confluences & Lessons Notes
                    const Text('Trade Notes & Confluences', style: TextStyle(fontSize: 11, color: AppTheme.textMuted)),
                    const SizedBox(height: 4),
                    TextField(
                      controller: notesCtrl,
                      maxLines: 3,
                      style: const TextStyle(color: Colors.white, fontSize: 12.5),
                      decoration: InputDecoration(
                        hintText: 'Key levels, session confluences, entry triggers, mistakes or lessons...',
                        hintStyle: const TextStyle(color: AppTheme.textDim, fontSize: 12),
                        filled: true,
                        fillColor: AppTheme.cardDark,
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                      ),
                    ),
                    const SizedBox(height: 18),

                    // Save Button
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.cyanAccent,
                          foregroundColor: Colors.black,
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                        ),
                        onPressed: () async {
                          await ApiService.updateJournal(
                            tradeId: tradeId,
                            notes: notesCtrl.text,
                            strategy: selectedStrategy,
                            rating: rating,
                            screenshot: screenshotCtrl.text,
                          );
                          Navigator.pop(ctx);
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Trade setup saved successfully!')),
                          );
                          _loadTrades();
                        },
                        child: const Text('SAVE TRADE SETUP', style: TextStyle(fontWeight: FontWeight.w900)),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Trade Journal Studio',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
        ),
      ),
      body: Column(
        children: [
          // Account Switcher Tabs
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              children: ['All Accounts', 'MT5 (Funded)', 'Capital.com (Real)'].map((acc) {
                final isSel = _selectedAccountTab == acc;
                return Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 3),
                    child: GestureDetector(
                      onTap: () {
                        setState(() => _selectedAccountTab = acc);
                        _loadTrades();
                      },
                      child: Container(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        decoration: BoxDecoration(
                          color: isSel ? AppTheme.cyanAccent.withOpacity(0.15) : AppTheme.surfaceDark,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: isSel ? AppTheme.cyanAccent.withOpacity(0.5) : AppTheme.cardBorder,
                          ),
                        ),
                        child: Text(
                          acc.replaceFirst(' (', '\n('),
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w800,
                            color: isSel ? AppTheme.cyanAccent : AppTheme.textMuted,
                          ),
                        ),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),

          // Trades List
          Expanded(
            child: _isLoading
                ? const ChartPulseLoader(message: 'FETCHING TRADE JOURNAL LOGS...')
                : _trades.isEmpty
                    ? const Center(
                        child: Text(
                          'No trade history found.',
                          style: TextStyle(color: AppTheme.textDim),
                        ),
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                        itemCount: _trades.length,
                        itemBuilder: (context, index) {
                          final tr = _trades[index];
                          final double profit = (tr['profit'] ?? 0.0).toDouble();
                          final bool isWin = profit >= 0;
                          final String sym = tr['symbol']?.toString() ?? 'ASSET';
                          final String side = (tr['type'] ?? 'BUY').toString().toUpperCase();
                          final double lots = (tr['lots'] ?? tr['volume'] ?? 0.01).toDouble();
                          final String closeTime = tr['close_time']?.toString().substring(0, 16) ?? '';
                          final String strategy = tr['setup_strategy']?.toString() ?? '';

                          return Container(
                            margin: const EdgeInsets.only(bottom: 8),
                            decoration: BoxDecoration(
                              color: AppTheme.cardDark,
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(
                                color: isWin
                                    ? AppTheme.cyanAccent.withOpacity(0.2)
                                    : AppTheme.tvRed.withOpacity(0.2),
                              ),
                            ),
                            child: ListTile(
                              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                              onTap: () => _openTradeStudio(tr),
                              leading: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                decoration: BoxDecoration(
                                  color: side == 'BUY'
                                      ? AppTheme.cyanAccent.withOpacity(0.12)
                                      : AppTheme.tvRed.withOpacity(0.12),
                                  borderRadius: BorderRadius.circular(6),
                                ),
                                child: Text(
                                  side,
                                  style: TextStyle(
                                    fontSize: 10,
                                    fontWeight: FontWeight.w900,
                                    color: side == 'BUY' ? AppTheme.cyanAccent : AppTheme.tvRed,
                                  ),
                                ),
                              ),
                              title: Row(
                                children: [
                                  Text(
                                    sym,
                                    style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    '${lots} Lots',
                                    style: const TextStyle(fontSize: 11, color: AppTheme.textDim),
                                  ),
                                  if (strategy.isNotEmpty) ...[
                                    const SizedBox(width: 8),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                                      decoration: BoxDecoration(
                                        color: AppTheme.goldAccent.withOpacity(0.15),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: Text(
                                        strategy,
                                        style: const TextStyle(
                                          fontSize: 9,
                                          fontWeight: FontWeight.w800,
                                          color: AppTheme.goldAccent,
                                        ),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                              subtitle: Text(
                                closeTime,
                                style: const TextStyle(fontSize: 10.5, color: AppTheme.textDim),
                              ),
                              trailing: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Text(
                                    '${isWin ? "+" : ""}\$${profit.toStringAsFixed(2)}',
                                    style: TextStyle(
                                      fontWeight: FontWeight.w900,
                                      fontSize: 13.5,
                                      color: isWin ? AppTheme.cyanAccent : AppTheme.tvRed,
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  const Text(
                                    'EDIT SETUP ›',
                                    style: TextStyle(fontSize: 9, color: AppTheme.textDim, fontWeight: FontWeight.w700),
                                  ),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
