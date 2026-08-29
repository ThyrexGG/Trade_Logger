import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppTheme {
  // Brand Color Tokens
  static const Color bgDark = Color(0xFF0E131F);
  static const Color surfaceDark = Color(0xFF131722);
  static const Color cardDark = Color(0xFF181C27);
  static const Color cardBorder = Color(0xFF2A2E39);
  
  static const Color cyanAccent = Color(0xFF00FFCC);
  static const Color neonLime = Color(0xFFBEF264);
  static const Color tvRed = Color(0xFFF23645);
  static const Color goldAccent = Color(0xFFFBBF24);
  
  static const Color textWhite = Color(0xFFFFFFFF);
  static const Color textMuted = Color(0xFF8A99AD);
  static const Color textDim = Color(0xFF64748B);

  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: bgDark,
      primaryColor: cyanAccent,
      cardColor: cardDark,
      textTheme: GoogleFonts.interTextTheme(
        ThemeData(brightness: Brightness.dark).textTheme,
      ).apply(
        bodyColor: textWhite,
        displayColor: textWhite,
      ),
      colorScheme: const ColorScheme.dark(
        primary: cyanAccent,
        secondary: neonLime,
        surface: surfaceDark,
        error: tvRed,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: surfaceDark,
        elevation: 0,
        centerTitle: false,
      ),
    );
  }
}
