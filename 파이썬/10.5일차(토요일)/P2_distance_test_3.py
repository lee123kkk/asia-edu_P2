import socket
import threading
import sys
import tty
import termios
import time

# [설정]
ESP32_IP = '192.168.0.9'
PORT = 8080
TICKS_PER_CM = 15.435  # ESP32와 동일한 설정값

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2.0)
    sock.connect((ESP32_IP, PORT))
    print(f"[{ESP32_IP}:{PORT}] 센서 퓨전 시스템 활성화 성공!")
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

def read_from_socket():
    global running
    while running:
        try:
            data = sock.recv(1024).decode('utf-8')
            if data:
                for line in data.split('\n'):
                    if "STATE:" in line:
                        # ESP32 데이터 파싱: "STATE: ... | Count A: ... | Count B: ... | Yaw: ..."
                        try:
                            parts = [p.strip() for p in line.split('|')]
                            state_raw = parts[0].replace("STATE:", "").strip()
                            count_a = int(parts[1].replace("Count A:", "").strip())
                            count_b = int(parts[2].replace("Count B:", "").strip())
                            yaw = float(parts[4].replace("Yaw:", "").strip())
                            
                            avg_ticks = (count_a + count_b) / 2
                            dist_cm = avg_ticks / TICKS_PER_CM
                            
                            display_state = STATE_MAP.get(state_raw, state_raw)
                            
                            # 상세 정보 출력
                            output = (f"\r[상태: {display_state: <15}] "
                                      f"거리: {dist_cm: >5.1f}cm | "
                                      f"회전각: {yaw: >6.1f}도 | "
                                      f"RawTicks: {int(avg_ticks)}       ")
                            sys.stdout.write(output)
                            sys.stdout.flush()
                        except:
                            pass
        except:
            running = False; break

read_thread = threading.Thread(target=read_from_socket, daemon=True)
read_thread.start()

def send_heartbeat():
    while running:
        try: sock.sendall(f"<{active_command}>".encode())
        except: break
        time.sleep(0.1)

threading.Thread(target=send_heartbeat, daemon=True).start()

print("\n" + "="*50)
print(" 🚀 [정밀 시퀀스 주행] 통제 단말기")
print(" - [g] : 시퀀스 주행 시작 (145cm -> 회전 -> 220cm)")
print(" - [x] : 즉시 정지 (E-STOP)")
print(" - [q] : 종료")
print("="*50 + "\n")

try:
    while running:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            char = sys.stdin.read(1).lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
            
        if char == 'q': break
        elif char in ['g', 'x']: active_command = char
finally:
    sock.close()
