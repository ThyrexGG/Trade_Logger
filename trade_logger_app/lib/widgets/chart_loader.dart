import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class ChartPulseLoader extends StatefulWidget {
  final String message;
  final double height;

  const ChartPulseLoader({
    Key? key,
    this.message = 'LOADING MARKET DATA...',
    this.height = 180,
  }) : super(key: key);

  @override
  State<ChartPulseLoader> createState() => _ChartPulseLoaderState();
}

class _ChartPulseLoaderState extends State<ChartPulseLoader> with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        height: widget.height,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            // Animated Candlestick Wave
            AnimatedBuilder(
              animation: _controller,
              builder: (context, child) {
                final val = _controller.value;
                return Row(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    _buildCandle(height: 18 + (12 * (1 - val)), color: AppTheme.cyanAccent),
                    const SizedBox(width: 6),
                    _buildCandle(height: 32 + (16 * val), color: AppTheme.neonLime),
                    const SizedBox(width: 6),
                    _buildCandle(height: 22 + (14 * (1 - val)), color: AppTheme.cyanAccent),
                    const SizedBox(width: 6),
                    _buildCandle(height: 38 + (10 * val), color: AppTheme.neonLime),
                    const SizedBox(width: 6),
                    _buildCandle(height: 16 + (14 * (1 - val)), color: AppTheme.tvRed),
                  ],
                );
              },
            ),
            const SizedBox(height: 16),

            // Pulsing Text Label
            Text(
              widget.message,
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w900,
                color: AppTheme.cyanAccent,
                letterSpacing: 1.2,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCandle({required double height, required Color color}) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Upper Wick
        Container(
          width: 1.5,
          height: 6,
          color: color.withOpacity(0.7),
        ),
        // Candle Body
        Container(
          width: 8,
          height: height,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(2),
            boxShadow: [
              BoxShadow(
                color: color.withOpacity(0.5),
                blurRadius: 8,
                spreadRadius: 1,
              ),
            ],
          ),
        ),
        // Lower Wick
        Container(
          width: 1.5,
          height: 6,
          color: color.withOpacity(0.7),
        ),
      ],
    );
  }
}
