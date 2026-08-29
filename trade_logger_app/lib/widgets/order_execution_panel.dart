import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../services/api_service.dart';

class OrderExecutionPanel extends StatefulWidget {
  final String symbol;
  final String accountId;
  
  const OrderExecutionPanel({
    Key? key, 
    required this.symbol,
    required this.accountId,
  }) : super(key: key);

  static void show(BuildContext context, String symbol, String accountId) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => OrderExecutionPanel(symbol: symbol, accountId: accountId),
    );
  }

  @override
  State<OrderExecutionPanel> createState() => _OrderExecutionPanelState();
}

class _OrderExecutionPanelState extends State<OrderExecutionPanel> {
  String _mode = 'Order'; // Order or DOM
  String _direction = 'Sell'; // Sell or Buy
  String _orderType = 'Market'; // Market, Limit, Stop
  
  final TextEditingController _priceController = TextEditingController(text: '159.976');
  final TextEditingController _riskController = TextEditingController(text: '3.28');
  
  bool _takeProfitEnabled = false;
  final TextEditingController _tpController = TextEditingController(text: '158.224');
  
  bool _stopLossEnabled = true;
  final TextEditingController _slController = TextEditingController(text: '161.728');
  
  bool _isSubmitting = false;

  void _submitOrder() async {
    setState(() => _isSubmitting = true);
    try {
      final res = await ApiService.executeOrder(
        symbol: widget.symbol,
        accountId: widget.accountId,
        direction: _direction.toUpperCase(),
        volume: 0.1, // Derive from risk eventually
        orderType: _orderType.toUpperCase(),
        price: double.tryParse(_priceController.text),
        stopLoss: _stopLossEnabled ? double.tryParse(_slController.text) : null,
        takeProfit: _takeProfitEnabled ? double.tryParse(_tpController.text) : null,
      );
      
      if (mounted) {
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(res['message'] ?? 'Order executed successfully'),
            backgroundColor: AppTheme.neonLime,
          )
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed: $e'),
            backgroundColor: AppTheme.tvRed,
          )
        );
      }
    } finally {
      if (mounted) setState(() => _isSubmitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final mq = MediaQuery.of(context);
    return Container(
      height: mq.size.height * 0.9,
      decoration: const BoxDecoration(
        color: Color(0xFF131313), // Deep dark matching screenshot
        borderRadius: BorderRadius.vertical(top: Radius.circular(12)),
      ),
      child: Column(
        children: [
          _buildHeader(),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 16),
                  _buildModeToggle(),
                  const SizedBox(height: 16),
                  _buildQuoteButtons(),
                  const SizedBox(height: 20),
                  _buildOrderTypeTabs(),
                  const SizedBox(height: 20),
                  _buildInputRow('Price', _priceController, 'Bid – 80'),
                  const SizedBox(height: 16),
                  _buildInputRow('Risk, USD', _riskController, '1.50 USD', showDropdown: true),
                  const SizedBox(height: 24),
                  _buildInfoBox(),
                  const SizedBox(height: 24),
                  _buildExitsSection(),
                  const SizedBox(height: 32),
                ],
              ),
            ),
          ),
          _buildExecuteButton(),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              const Icon(Icons.currency_exchange, color: Color(0xFFD97757), size: 24),
              const SizedBox(width: 8),
              Text(
                widget.symbol,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          Row(
            children: [
              IconButton(
                icon: const Icon(Icons.grid_view, color: AppTheme.textMuted),
                onPressed: () {},
              ),
              IconButton(
                icon: const Icon(Icons.more_horiz, color: AppTheme.textMuted),
                onPressed: () {},
              ),
              IconButton(
                icon: const Icon(Icons.close, color: AppTheme.textMuted),
                onPressed: () => Navigator.pop(context),
              ),
            ],
          )
        ],
      ),
    );
  }

  Widget _buildModeToggle() {
    return Container(
      height: 40,
      decoration: BoxDecoration(
        color: const Color(0xFF1E1E1E),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        children: ['Order', 'DOM'].map((mode) {
          final isSelected = _mode == mode;
          return Expanded(
            child: GestureDetector(
              onTap: () => setState(() => _mode = mode),
              child: Container(
                decoration: BoxDecoration(
                  color: isSelected ? const Color(0xFF333333) : Colors.transparent,
                  borderRadius: BorderRadius.circular(6),
                ),
                alignment: Alignment.center,
                child: Text(
                  mode,
                  style: TextStyle(
                    color: isSelected ? Colors.white : AppTheme.textMuted,
                    fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                  ),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildQuoteButtons() {
    return Row(
      children: [
        // Sell Button
        Expanded(
          child: GestureDetector(
            onTap: () => setState(() => _direction = 'Sell'),
            child: Container(
              height: 60,
              decoration: BoxDecoration(
                color: _direction == 'Sell' ? const Color(0xFF4A1A22) : const Color(0xFF2A151A),
                borderRadius: const BorderRadius.horizontal(left: Radius.circular(8)),
                border: Border.all(
                  color: _direction == 'Sell' ? AppTheme.tvRed : Colors.transparent,
                  width: 1,
                )
              ),
              child: Stack(
                children: [
                  Positioned(
                    left: 12, top: 8,
                    child: Text('Sell', style: TextStyle(color: AppTheme.tvRed.withOpacity(0.9), fontSize: 13, fontWeight: FontWeight.bold)),
                  ),
                  Positioned(
                    left: 12, bottom: 8,
                    child: Text('160.056', style: TextStyle(color: AppTheme.tvRed.withOpacity(0.9), fontSize: 18, fontWeight: FontWeight.bold)),
                  ),
                ],
              ),
            ),
          ),
        ),
        // Spread Badge
        Container(
          width: 32,
          height: 24,
          color: const Color(0xFF111111),
          alignment: Alignment.center,
          child: const Text('7.0', style: TextStyle(color: AppTheme.textMuted, fontSize: 12)),
        ),
        // Buy Button
        Expanded(
          child: GestureDetector(
            onTap: () => setState(() => _direction = 'Buy'),
            child: Container(
              height: 60,
              decoration: BoxDecoration(
                color: _direction == 'Buy' ? const Color(0xFF1A354A) : const Color(0xFF15222A),
                borderRadius: const BorderRadius.horizontal(right: Radius.circular(8)),
                border: Border.all(
                  color: _direction == 'Buy' ? Colors.blueAccent : Colors.transparent,
                  width: 1,
                )
              ),
              child: Stack(
                children: [
                  Positioned(
                    right: 12, top: 8,
                    child: Text('Buy', style: TextStyle(color: Colors.blueAccent.withOpacity(0.9), fontSize: 13, fontWeight: FontWeight.bold)),
                  ),
                  Positioned(
                    right: 12, bottom: 8,
                    child: Text('160.126', style: TextStyle(color: Colors.blueAccent.withOpacity(0.9), fontSize: 18, fontWeight: FontWeight.bold)),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildOrderTypeTabs() {
    return Container(
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: Color(0xFF333333))),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: ['Market', 'Limit', 'Stop'].map((type) {
          final isSelected = _orderType == type;
          return GestureDetector(
            onTap: () => setState(() => _orderType = type),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
              decoration: BoxDecoration(
                border: Border(bottom: BorderSide(color: isSelected ? Colors.white : Colors.transparent, width: 2)),
              ),
              child: Text(
                type,
                style: TextStyle(
                  color: isSelected ? Colors.white : AppTheme.textMuted,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildInputRow(String label, TextEditingController controller, String suffixText, {bool showDropdown = false}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(label, style: const TextStyle(color: AppTheme.textMuted, fontSize: 13)),
            if (showDropdown) const Icon(Icons.keyboard_arrow_down, color: AppTheme.textMuted, size: 16),
          ],
        ),
        const SizedBox(height: 8),
        Container(
          height: 44,
          decoration: BoxDecoration(
            color: const Color(0xFF131313),
            border: Border.all(color: const Color(0xFF333333)),
            borderRadius: BorderRadius.circular(6),
          ),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: controller,
                  style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold),
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(
                    border: InputBorder.none,
                    contentPadding: EdgeInsets.symmetric(horizontal: 12),
                  ),
                ),
              ),
              const Icon(Icons.sync_alt, color: AppTheme.textMuted, size: 16),
              const SizedBox(width: 12),
              Text(suffixText, style: const TextStyle(color: AppTheme.textMuted, fontSize: 13)),
              if (showDropdown) const Icon(Icons.keyboard_arrow_down, color: AppTheme.textMuted, size: 16),
              const SizedBox(width: 8),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildInfoBox() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1A1A),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        children: [
          _buildInfoRow('Trade value (200:1)', '299.72 USD', true),
          const SizedBox(height: 8),
          _buildInfoRow('Available margin', '294.03 USD', true),
          const SizedBox(height: 8),
          _buildInfoRow('Pip value', '0.02 USD', true),
        ],
      ),
    );
  }

  Widget _buildInfoRow(String label, String val, bool highlightVal) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: const TextStyle(color: AppTheme.textMuted, fontSize: 13)),
        Text(val, style: TextStyle(color: highlightVal ? Colors.white : AppTheme.textMuted, fontSize: 13, fontWeight: FontWeight.bold)),
      ],
    );
  }

  Widget _buildExitsSection() {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text('Exits', style: TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold)),
            const Icon(Icons.keyboard_arrow_up, color: AppTheme.textMuted),
          ],
        ),
        const SizedBox(height: 16),
        _buildExitControl('Take profit, price', _tpController, _takeProfitEnabled, (val) => setState(() => _takeProfitEnabled = val)),
        const SizedBox(height: 16),
        _buildExitControl('Stop loss, price', _slController, _stopLossEnabled, (val) => setState(() => _stopLossEnabled = val)),
        const SizedBox(height: 16),
        _buildInfoRow('Risk / Reward', '1', true),
      ],
    );
  }

  Widget _buildExitControl(String label, TextEditingController controller, bool enabled, Function(bool) onToggle) {
    return Column(
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                Text(label, style: const TextStyle(color: AppTheme.textMuted, fontSize: 13)),
                const Icon(Icons.keyboard_arrow_down, color: AppTheme.textMuted, size: 16),
              ],
            ),
            Switch(
              value: enabled,
              onChanged: onToggle,
              activeColor: Colors.white,
              activeTrackColor: const Color(0xFF444444),
              inactiveThumbColor: const Color(0xFF666666),
              inactiveTrackColor: const Color(0xFF222222),
            ),
          ],
        ),
        if (enabled)
          Container(
            height: 44,
            decoration: BoxDecoration(
              color: const Color(0xFF131313),
              border: Border.all(color: const Color(0xFF333333)),
              borderRadius: BorderRadius.circular(6),
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: controller,
                    style: const TextStyle(color: Colors.white, fontSize: 15, fontWeight: FontWeight.bold),
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(
                      border: InputBorder.none,
                      contentPadding: EdgeInsets.symmetric(horizontal: 12),
                    ),
                  ),
                ),
                const Icon(Icons.sync_alt, color: AppTheme.textMuted, size: 16),
                const SizedBox(width: 12),
                const Text('175.2 pips', style: TextStyle(color: AppTheme.textMuted, fontSize: 13)),
                const Icon(Icons.keyboard_arrow_down, color: AppTheme.textMuted, size: 16),
                const SizedBox(width: 8),
              ],
            ),
          ),
      ],
    );
  }

  Widget _buildExecuteButton() {
    final bgColor = _direction == 'Sell' ? AppTheme.tvRed : Colors.blueAccent;
    final price = _orderType == 'Market' ? (_direction == 'Sell' ? '160.056' : '160.126') : _priceController.text;
    
    return Container(
      padding: EdgeInsets.only(
        left: 16, right: 16, top: 16, 
        bottom: MediaQuery.of(context).padding.bottom + 16
      ),
      decoration: const BoxDecoration(
        color: Color(0xFF131313),
        border: Border(top: BorderSide(color: Color(0xFF2A2E39))),
      ),
      child: ElevatedButton(
        onPressed: _isSubmitting ? null : _submitOrder,
        style: ElevatedButton.styleFrom(
          backgroundColor: bgColor,
          foregroundColor: Colors.white,
          disabledBackgroundColor: bgColor.withOpacity(0.5),
          minimumSize: const Size(double.infinity, 56),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
          elevation: 0,
        ),
        child: _isSubmitting 
          ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
          : Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  _direction,
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 2),
                Text(
                  '300 ${widget.symbol} @ $price ${_orderType.toUpperCase()}',
                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.normal),
                ),
              ],
            ),
      ),
    );
  }
}
