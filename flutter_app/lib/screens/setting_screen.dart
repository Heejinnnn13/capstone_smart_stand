import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class SettingScreen extends StatelessWidget {
  const SettingScreen({super.key});

  Future<void> sendTestRequest() async {
    final url = Uri.parse('http://192.168.77.138:5000/led');

    try {
      await http.post(
        url,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'state': 'on'}),
      );
    } catch (e) {
      debugPrint("HTTP Error: $e");
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,

      appBar: AppBar(
        backgroundColor: const Color(0xFFD9D9D9),
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.black), // ← 뒤로가기 색
        title: Row(
          children: const [
            Text(
              "Setting",
              style: TextStyle(
                color: Colors.black,
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
            SizedBox(width: 6),
            Icon(
              Icons.lightbulb,
              color: Color(0xFFFFD54F),
              size: 22,
            ),
          ],
        ),
      ),

      body: Center(
        child: ElevatedButton(
          onPressed: sendTestRequest,
          style: ElevatedButton.styleFrom(
            backgroundColor: Colors.black,
            padding: const EdgeInsets.symmetric(
              horizontal: 24,
              vertical: 14,
            ),
          ),
          child: const Text(
            "TEST: LED ON",
            style: TextStyle(color: Colors.white),
          ),
        ),
      ),
    );
  }
}