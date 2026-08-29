import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/chart_loader.dart';

class SymbolSearchScreen extends StatefulWidget {
  const SymbolSearchScreen({Key? key}) : super(key: key);

  @override
  State<SymbolSearchScreen> createState() => _SymbolSearchScreenState();
}

class _SymbolSearchScreenState extends State<SymbolSearchScreen> {
  bool _isLoading = true;
  List<Map<String, dynamic>> _symbols = [];
  String _searchQuery = '';
  String _selectedCategory = 'All';

  @override
  void initState() {
    super.initState();
    _loadSymbols();
  }

  Future<void> _loadSymbols() async {
    setState(() => _isLoading = true);
    final symbols = await ApiService.getSymbols();
    if (mounted) {
      setState(() {
        _symbols = symbols;
        _isLoading = false;
      });
    }
  }

  Future<void> _toggleFavorite(String symbol) async {
    // Instant optimistic UI toggle
    setState(() {
      for (var s in _symbols) {
        if (s['id'] == symbol) {
          s['is_flagged'] = !(s['is_flagged'] ?? false);
        }
      }
      // Re-sort with flagged at top
      final flagged = _symbols.where((s) => s['is_flagged'] == true).toList();
      final unflagged = _symbols.where((s) => s['is_flagged'] != true).toList();
      _symbols = [...flagged, ...unflagged];
    });

    await ApiService.toggleFavoriteSymbol(symbol);
  }

  void _openSetAlertModal(Map<String, dynamic> asset) {
    final TextEditingController priceCtrl = TextEditingController(text: '2510.0');
    final TextEditingController notesCtrl = TextEditingController();
    String condition = 'ABOVE';

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
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        'SET ALERT: ${asset['display']}',
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w800,
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
                  const Text('Target Price (\$)', style: TextStyle(fontSize: 11, color: AppTheme.textMuted)),
                  const SizedBox(height: 4),
                  TextField(
                    controller: priceCtrl,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    style: const TextStyle(color: Colors.white, fontSize: 14),
                    decoration: InputDecoration(
                      filled: true,
                      fillColor: AppTheme.cardDark,
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Text('Condition', style: TextStyle(fontSize: 11, color: AppTheme.textMuted)),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Expanded(
                        child: ChoiceChip(
                          label: const Text('Rose Above (>=)'),
                          selected: condition == 'ABOVE',
                          onSelected: (val) => setModalState(() => condition = 'ABOVE'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: ChoiceChip(
                          label: const Text('Dropped Below (<=)'),
                          selected: condition == 'BELOW',
                          onSelected: (val) => setModalState(() => condition = 'BELOW'),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  const Text('Alert Notes', style: TextStyle(fontSize: 11, color: AppTheme.textMuted)),
                  const SizedBox(height: 4),
                  TextField(
                    controller: notesCtrl,
                    style: const TextStyle(color: Colors.white, fontSize: 13),
                    decoration: InputDecoration(
                      hintText: 'e.g. Key 4H resistance breakout',
                      hintStyle: const TextStyle(color: AppTheme.textDim, fontSize: 12),
                      filled: true,
                      fillColor: AppTheme.cardDark,
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                    ),
                  ),
                  const SizedBox(height: 18),
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
                        final double? price = double.tryParse(priceCtrl.text);
                        if (price != null) {
                          await ApiService.createAlert(
                            asset['id'],
                            price,
                            condition,
                            notesCtrl.text,
                          );
                          Navigator.pop(ctx);
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Price alert created for ${asset['id']}!')),
                          );
                        }
                      },
                      child: const Text('CONFIRM ALERT', style: TextStyle(fontWeight: FontWeight.w900)),
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    // Filter symbols based on category & search query
    final filtered = _symbols.where((item) {
      final matchesCat = _selectedCategory == 'All' ||
          item['cat']?.toString().toLowerCase() == _selectedCategory.toLowerCase();
      final q = _searchQuery.toUpperCase().trim();
      final matchesQ = q.isEmpty ||
          (item['id']?.toString().toUpperCase().contains(q) ?? false) ||
          (item['desc']?.toString().toUpperCase().contains(q) ?? false) ||
          (item['display']?.toString().toUpperCase().contains(q) ?? false);
      return matchesCat && matchesQ;
    }).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Symbol search',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800),
        ),
      ),
      body: _isLoading
          ? const ChartPulseLoader(message: 'SYNCING WATCHLIST TICKERS...')
          : Column(
              children: [
                // 1. Search Bar
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: TextField(
                    onChanged: (val) => setState(() => _searchQuery = val),
                    style: const TextStyle(color: Colors.white, fontSize: 13),
                    decoration: InputDecoration(
                      hintText: 'Symbol, ISIN, or CUSIP',
                      hintStyle: const TextStyle(color: AppTheme.textDim, fontSize: 13),
                      prefixIcon: const Icon(Icons.search, color: AppTheme.textMuted, size: 18),
                      filled: true,
                      fillColor: AppTheme.surfaceDark,
                      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: const BorderSide(color: AppTheme.cardBorder),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: const BorderSide(color: Color(0xFF2962FF)),
                      ),
                    ),
                  ),
                ),

                // 2. Category Filter Pills
                SizedBox(
                  height: 38,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    children: ['All', 'Forex', 'Indices', 'Commodities', 'Crypto'].map((cat) {
                      final isSelected = _selectedCategory == cat;
                      return Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: GestureDetector(
                          onTap: () => setState(() => _selectedCategory = cat),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                            decoration: BoxDecoration(
                              color: isSelected ? Colors.white : AppTheme.surfaceDark,
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(
                                color: isSelected ? Colors.white : AppTheme.cardBorder,
                              ),
                            ),
                            child: Text(
                              cat,
                              style: TextStyle(
                                fontSize: 11.5,
                                fontWeight: FontWeight.w700,
                                color: isSelected ? Colors.black : AppTheme.textMuted,
                              ),
                            ),
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                ),
                const SizedBox(height: 10),

                // 3. TradingView Symbol List
                Expanded(
                  child: ListView.builder(
                    itemCount: filtered.length,
                    itemBuilder: (context, index) {
                      final item = filtered[index];
                      final isFlagged = item['is_flagged'] == true;

                      // Parse color
                      Color iconBg = const Color(0xFF06B6D4);
                      try {
                        String hex = item['icon_bg']?.toString().replaceAll('#', '') ?? '06B6D4';
                        iconBg = Color(int.parse('0xFF$hex'));
                      } catch (e) {}

                      return Container(
                        decoration: const BoxDecoration(
                          border: Border(bottom: BorderSide(color: Color(0xFF1E222D), width: 1)),
                        ),
                        child: ListTile(
                          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
                          onTap: () => _openSetAlertModal(item),
                          leading: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              // Interactive Red Ribbon Flag Notch
                              GestureDetector(
                                onTap: () => _toggleFavorite(item['id']),
                                child: Container(
                                  width: 24,
                                  height: 32,
                                  alignment: Alignment.centerLeft,
                                  child: CustomPaint(
                                    size: const Size(9, 16),
                                    painter: RibbonPainter(
                                      color: isFlagged ? AppTheme.tvRed : Colors.white.withOpacity(0.15),
                                      isFlagged: isFlagged,
                                    ),
                                  ),
                                ),
                              ),
                              const SizedBox(width: 4),

                              // Asset Icon Circle
                              Container(
                                width: 24,
                                height: 24,
                                decoration: BoxDecoration(
                                  color: iconBg,
                                  shape: BoxShape.circle,
                                ),
                                alignment: Alignment.center,
                                child: Text(
                                  item['icon_txt'] ?? '',
                                  style: const TextStyle(
                                    fontSize: 8.5,
                                    fontWeight: FontWeight.w900,
                                    color: Colors.white,
                                  ),
                                ),
                              ),
                            ],
                          ),
                          title: Row(
                            children: [
                              Text(
                                item['display'] ?? '',
                                style: const TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                ),
                              ),
                            ],
                          ),
                          subtitle: Text(
                            item['desc'] ?? '',
                            style: const TextStyle(fontSize: 11.5, color: AppTheme.textMuted),
                          ),
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                item['type'] ?? '',
                                style: const TextStyle(fontSize: 10, color: AppTheme.textDim),
                              ),
                              const SizedBox(width: 6),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                decoration: BoxDecoration(
                                  color: const Color(0xFF262B38),
                                  borderRadius: BorderRadius.circular(4),
                                ),
                                child: const Text(
                                  'Capital.com',
                                  style: TextStyle(
                                    fontSize: 9.5,
                                    fontWeight: FontWeight.w700,
                                    color: Color(0xFFB2B5BE),
                                  ),
                                ),
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

// Custom Painter for TradingView Red Ribbon Bookmark Notch
class RibbonPainter extends CustomPainter {
  final Color color;
  final bool isFlagged;

  RibbonPainter({required this.color, required this.isFlagged});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.fill;

    if (isFlagged) {
      paint.maskFilter = const MaskFilter.blur(BlurStyle.solid, 1.5);
    }

    final path = Path()
      ..moveTo(0, 0)
      ..lineTo(size.width, 0)
      ..lineTo(size.width, size.height)
      ..lineTo(size.width / 2, size.height * 0.72)
      ..lineTo(0, size.height)
      ..close();

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant RibbonPainter oldDelegate) {
    return oldDelegate.color != color || oldDelegate.isFlagged != isFlagged;
  }
}
