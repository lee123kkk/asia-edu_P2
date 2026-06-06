import socket
import threading
import sys
import tty
import termios
import time

# [설정]
ESP32_IP = '192.168.0.9'
PORT = 8080
TICKS_PER_CM = 15.435  

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2.0)
    sock.connect((ESP32_IP, PORT))
    print(f"[{ESP32_IP}:{PORT}] 시스템 연결 성공!")
except Exception as e:
    print(f"접속 에러: {e}")
    sys.exit()

active_command = 'x'
running = True

# 상태 해석용 맵
STATE_MAP = {
    "DRIVE_1": "1차 주행 (145cm)",
    "WAIT_1":  "1차 안정화 대기",
    "TURN_CCW": "90도 회전 중",
    "WAIT_2":  "2차 안정화 대기",
    "DRIVE_2": "2차 주행 (220cm)",
    "ARRIVED": "주행 완료 (ARRIVED)"
}

# 1. 수신 스레드 (로그가 쌓이도록 수정)
def read_from_socket():
    global running
    while running:
        try:
            data = sock.recv(1024).decode('utf-8')
            if data:
                for line in data.split('\n'):
                    if "STATE:" in line:
                        try:
                            parts = [p.strip() for p in line.split('|')]
                            state_raw = parts[0].replace("STATE:", "").strip()
                            count_a = int(parts[1].replace("Count A:", "").strip())
                            count_b = int(parts[2].replace("Count B:", "").strip())
                            # 회전 중일 때는 TurnAcc, 직진 중일 때는 Yaw 데이터를 파싱
                            yaw_data = parts[3].replace("Yaw:", "").strip()
                            
                            avg_ticks = (count_a + count_b) / 2
                            dist_cm = avg_ticks / TICKS_PER_CM
                            display_state = STATE_MAP.get(state_raw, state_raw)
                            
                            # ★ [핵심 수정] 줄바꿈(\n)을 사용하여 이전 로그를 유지함
                            log_msg = f"[{time.strftime('%H:%M:%S')}] {display_state: <15} | 거리: {dist_cm: >5.1f}cm | 각도: {yaw_data: >6.1f}도 | Ticks: {int(avg_ticks)}"
                            print(log_msg)
                            
                        except:
                            pass
            else:
                raise Exception("연결 끊김.")
        except Exception as e:
            print(f"\n🚨 통신 장애: {e}")
            running = False; break

read_thread = threading.Thread(target=read_from_socket, daemon=True)
read_thread.start()

# 2. 하트비트 송신
def send_heartbeat():
    while running:
        try: sock.sendall(f"<{active_command}>".encode())
        except: break
        time.sleep(0.1)

threading.Thread(target=send_heartbeat, daemon=True).start()

# 3. 터미널 제어
def get_char():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

print("\n" + "="*60)
print(" 🚀 [정밀 시퀀스 로그 모드] 모든 과정이 터미널에 기록됩니다.")
print(" - [g] : 시작 | [x] : 긴급 정지 | [q] : 종료")
print("="*60 + "\n")

try:
    while running:
        char = get_char().lower()
        if char == 'q': break
        elif char in ['g', 'x']: active_command = char
finally:
    running = False
    sock.close()
