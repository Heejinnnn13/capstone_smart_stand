import 'package:flutter/material.dart';
import 'screens/splash_screen.dart';

void main() {
  runApp(const StudyLightApp());
}

class StudyLightApp extends StatelessWidget {
  const StudyLightApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Study Light',
      theme: ThemeData(primarySwatch: Colors.blueGrey),
      home: SplashScreen(),
    );
  }
}