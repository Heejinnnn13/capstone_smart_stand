import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'setting_screen.dart';

// ================= 교육과정 enum =================
enum SchoolLevel {
  elementary,
  middle,
  high,
}

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  // ================= 상태 변수 =================
  bool httpConnectEnabled = false;
  bool isHttpAlive = false;
  bool isLedOn = false;

  int lightLevel = 3; // Brightness level: 1 ~ 5
  SchoolLevel selectedLevel = SchoolLevel.middle;

  final String baseUrl = "http://192.168.77.17:5000";

  // ================= HTTP 상태 확인 =================
  Future<void> checkHttpStatus() async {
    if (!httpConnectEnabled) {
      setState(() {
        isHttpAlive = false;
      });
      return;
    }

    try {
      final response = await http
          .get(Uri.parse("$baseUrl/ping"))
          .timeout(const Duration(seconds: 2));

      setState(() {
        isHttpAlive = response.statusCode == 200;
      });
    } catch (_) {
      setState(() {
        isHttpAlive = false;
      });
    }
  }

  // ================= LED ON / OFF =================
  Future<void> toggleLed(bool on) async {
    if (!httpConnectEnabled) return;

    try {
      final response = await http.post(
        Uri.parse("$baseUrl/led"),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'state': on ? 'on' : 'off'}),
      ).timeout(const Duration(seconds: 3)); // 추가

      if (response.statusCode == 200) {
        setState(() {
          isLedOn = on;
          isHttpAlive = true; // ✅ LED 제어 성공 = 서버 살아있음
        });
      }
    } catch (e) {
      debugPrint("LED HTTP error: $e");
    }
  }

  // ================= 밝기 서버 전송 =================
  Future<void> sendBrightness(int level) async {
    if (!httpConnectEnabled || !isLedOn) return;

    try {
      await http.post(
        Uri.parse("$baseUrl/brightness"),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'light_level': level}),
      ).timeout(const Duration(seconds: 3)); // 추가
    } catch (e) {
      debugPrint("Brightness HTTP error: $e");
    }
  }

  void increaseBrightness() {
    if (!isLedOn) return; // 추가
    if (lightLevel < 5) {
      setState(() { lightLevel++; });
      sendBrightness(lightLevel);
    }
  }

  void decreaseBrightness() {
    if (!isLedOn) return; // 추가
    if (lightLevel > 1) {
      setState(() { lightLevel--; });
      sendBrightness(lightLevel);
    }
  }

  // ================= 교육과정 서버 전송 =================
  Future<void> sendEducationLevel(SchoolLevel level) async {
    if (!httpConnectEnabled) return;

    String levelStr;
    switch (level) {
      case SchoolLevel.elementary:
        levelStr = "elementary";
        break;
      case SchoolLevel.middle:
        levelStr = "middle";
        break;
      case SchoolLevel.high:
        levelStr = "high";
        break;
    }

    try {
      await http.post(
        Uri.parse("$baseUrl/set_level"),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'education_level': levelStr}),
      ).timeout(const Duration(seconds: 3)); // 추가
    } catch (_) {
      setState(() {
        isHttpAlive = false;
      });
    }
  }

  // ================= UI =================
  @override
  Widget build(BuildContext context) {
    final bool showHttpAlive = httpConnectEnabled && isHttpAlive;

    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: const Color(0xFFD9D9D9),
        elevation: 0,
        title: Row(
          children: const [
            Text(
              "Study Light",
              style: TextStyle(
                color: Colors.black,
                fontSize: 18,
                fontWeight: FontWeight.w600,
              ),
            ),
            SizedBox(width: 6),
            Icon(Icons.lightbulb, color: Color(0xFFFFD54F)),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings, color: Colors.black),
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => const SettingScreen(),
                ),
              );
            },
          ),
        ],
      ),

      body: Column(
        children: [
          const SizedBox(height: 24),

          // ================= 카드 영역 =================
          Container(
            margin: const EdgeInsets.symmetric(horizontal: 20),
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: const Color(0xFFF5F5F5),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Column(
              children: [
                // ================= HTTP Status =================
                Row(
                  children: [
                    const Text("HTTP Status", style: TextStyle(fontSize: 16)),
                    const Spacer(),
                    Row(
                      children: [
                        _statusDot(Colors.green, showHttpAlive),
                        const SizedBox(width: 8),
                        _statusDot(Colors.red, !showHttpAlive),
                      ],
                    ),
                  ],
                ),

                const SizedBox(height: 16),

                // ================= HTTP Connect =================
                Row(
                  children: [
                    const Text("HTTP Connect", style: TextStyle(fontSize: 16)),
                    const Spacer(),
                    Switch(
                      value: httpConnectEnabled,
                      onChanged: (value) async {
                        if (value) {
                          setState(() {
                            httpConnectEnabled = true;
                          });
                          await checkHttpStatus();
                        } else {
                          if (isLedOn) {
                            await toggleLed(false); // 서버에 LED OFF 신호 먼저
                          }
                          setState(() {
                            httpConnectEnabled = false;
                            isHttpAlive = false;
                            isLedOn = false;
                          });
                        }
                      },
                    ),
                  ],
                ),

                const SizedBox(height: 16),

                // ================= Light Level =================
                Row(
                  children: [
                    const Text("Light Level", style: TextStyle(fontSize: 16)),
                    const Spacer(),
                    Row(
                      children: [
                        IconButton(
                          onPressed: decreaseBrightness,
                          icon: const Icon(Icons.remove),
                        ),
                        Text(
                          lightLevel.toString(),
                          style: const TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        IconButton(
                          onPressed: increaseBrightness,
                          icon: const Icon(Icons.add),
                        ),
                      ],
                    ),
                  ],
                ),

                const SizedBox(height: 16),

                // ================= 교육과정 선택 =================
                Row(
                  children: [
                    const Text("교육과정", style: TextStyle(fontSize: 16)),
                    const Spacer(),
                    _schoolButton("초등", SchoolLevel.elementary),
                    const SizedBox(width: 8),
                    _schoolButton("중등", SchoolLevel.middle),
                    const SizedBox(width: 8),
                    _schoolButton("고등", SchoolLevel.high),
                  ],
                ),
              ],
            ),
          ),

          const Spacer(),

          // ================= 전원 버튼 =================
          IconButton(
            iconSize: 80,
            icon: Icon(
              Icons.power_settings_new,
              color: isLedOn ? Colors.green : Colors.black,
            ),
            onPressed: () {
              toggleLed(!isLedOn);
            },
          ),

          const SizedBox(height: 40),
        ],
      ),
    );
  }

  // ================= 교육과정 버튼 =================
  Widget _schoolButton(String label, SchoolLevel level) {
    final bool isSelected = selectedLevel == level;

    return GestureDetector(
      onTap: () {
        setState(() {
          selectedLevel = level;
        });
        sendEducationLevel(level);
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        decoration: BoxDecoration(
          color: isSelected ? Colors.black : Colors.transparent,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: Colors.black),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: isSelected ? Colors.white : Colors.black,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }

  // ================= 상태 점 =================
  Widget _statusDot(Color color, bool active) {
    return Container(
      width: 16,
      height: 16,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: active ? color : Colors.grey.shade400,
      ),
    );
  }
}