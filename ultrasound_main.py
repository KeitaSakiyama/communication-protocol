import matplotlib
matplotlib.use('Qt5Agg')

import pyaudio
import numpy as np
import threading
import codecs
from pylab import *
import time

import communicationControl

######### ここからパラメータ設定
# データ送受信に使用する音の周波数設定
# （Frequency Shift Keyingで変調するので2種類使う）
FREQUENCY0 = 2500
FREQUENCY1 = 3500
# 送受信ビットレート（bit per second）
# （マンチェスター符号が有効の場合実効レートは半分になる）
BPS = 50
# マンチェスタ符号化有無
IS_MANCHESTER = True

# 再生音量（最大1.0）
VOLUME = 0.7
# 複数のマイク/スピーカーがある場合はここでINDEXを設定する
INPUT_DEVICE_INDEX = 0
OUTPUT_DEVICE_INDEX = 1
# 録音データを（CHUNK/SAMPLING_RATE）秒ごとに処理する
#CHUNK = 32768 #for Win10
CHUNK = 8192 #for MacOS
# 再生/録音サンプリングレート
SAMPLING_RATE = 48000             # sampling frequency [Hz]
# 再生チャネル （多分変更しなくて良い）
CHANNELS = 1             # monaural
# 音声データフォーマット
FORMAT = pyaudio.paFloat32 # Float 32bit mode
#FORMAT = pyaudio.paInt16 # Int 16bit mode, 演算を軽くしたいとき用

# デバッグ用（録音データ保存）
DEBUG_MODE = False
#DEBUG_MODE = True

IS_PLOT = True
DOWNSAMPLE = 8
PLOT_LEN = int(65536 / CHUNK)
######### ここまでパラメータ設定

def tx_data_read(filename, tx_data):
    """ファイルからビットパターンを読み込む"""
    tx_data.clear()
    fp = codecs.open(filename, 'r')
    for idx, line in enumerate(fp):
        split_data = line.rstrip('\r\n').split(',')
        for bit in split_data:
            try:
                tx_data.append(int(bit))
            except:
                print(f"Illegal input file format: {bit} in {idx}:{line}")
    fp.close()

def wait_input(cc, tx_data):
    """キーボード入力で状態制御"""
    # global state
    while cc.state != "EXIT":
        print("Command input >", end="")
        key = input()
        if len(key) == 0:
            continue
        if key[0] == "e":
            cc.state = "EXIT"
        elif key[0] == "t":
            try:
                inputfileidx = int(key[1])
                if 1 <= inputfileidx and inputfileidx <= 3:
                    inputfilename = f"test{inputfileidx}.txt"
                else:
                    inputfilename = "test1.txt"
            except:
                inputfilename = "test1.txt"
            tx_data_read(inputfilename, tx_data)
            print(f"{inputfilename}: {tx_data}")
            cc.state = "TX"
        elif key[0] == "r":
            cc.state = "RX"
        elif key[0] == "i":
            cc.state = "INIT"
        elif key[0] == "c":
            cc.state = "CALIBRATION"
        elif key[0] == "p":
            print(f"current state = {cc.state}")
        else:
            cc.state = cc.state
        print(f"input = {key}")
        print(f"state = {cc.state}")

def pyaudio_init():
    """音声入出力ストリームの初期化"""
    paudio = pyaudio.PyAudio()

    # 複数のマイク/スピーカーがある場合、以下のfor文で確認して
    # INPUT_DEVICE_INDEXとOUTPUT_DEVICE_INDEXを書き換える
    for x in range(0, paudio.get_device_count()): 
        print(paudio.get_device_info_by_index(x))
        print("\n")

    inputstream = paudio.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=SAMPLING_RATE,
                    input=True,
                    input_device_index=INPUT_DEVICE_INDEX,
                    frames_per_buffer=CHUNK)

    outputstream = paudio.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=SAMPLING_RATE,
                    output=True,
                    output_device_index=OUTPUT_DEVICE_INDEX,
                    frames_per_buffer=CHUNK)

    return paudio, inputstream, outputstream

def pyaudio_finish(paudio, inputstream, outputstream):
    """音声入出力ストリームを閉じる"""
    inputstream.stop_stream()
    inputstream.close()
    outputstream.stop_stream()
    outputstream.close()
    paudio.terminate()

def rec_sound(inputstream):
    """録音（受信）"""
    #rx_data = inputstream.read(CHUNK)
    rx_data = inputstream.read(CHUNK, exception_on_overflow=False)
    if FORMAT == pyaudio.paInt16:
        audioarray = np.frombuffer(rx_data, dtype="int16") / float(2 ** 15)
    else:
        audioarray = np.frombuffer(rx_data, dtype="float32")
    return audioarray

def play_sound(outputstream, tx_data):
    """再生（送信）"""
    tx_data *= VOLUME
    if FORMAT == pyaudio.paInt16:
        outputstream.write((tx_data * (2 ** 15)).astype(np.int16).tostring())
    else:
        outputbytes = tx_data.astype(np.float32).tobytes()
        outputstream.write(outputbytes)
    outputstream.stop_stream()

def print_rx_data(rx_result):
    if len(rx_result) > 8:
        print(rx_result)
        width = 0
        height = 0
        for i in range(4):
            width += (rx_result[i] << (3 - i))
            height += (rx_result[i + 4] << (3 - i))
        print(f"width{width}, height{height}")
        for i in range(height):
            for j in range(width):
                if i * width + j + 8 < len(rx_result):
                    if rx_result[i * width + j + 8] == 0:
                        print("□", end='')
                    else:
                        print("■", end='')
                else:
                    print("*", end='')
            print(" ")

if __name__ == "__main__":
    # スピーカーとマイクによる入出力を設定
    paudio, inputstream, outputstream = pyaudio_init()

    # 通信制御用クラスのインスタンスを作る
    cc = communicationControl.CommunicationControl(FREQUENCY0, FREQUENCY1, SAMPLING_RATE, BPS, IS_MANCHESTER)

    #送信データ保存用
    tx_data = []

    # 別スレッドでキーボード入力処理
    th = threading.Thread(target=wait_input, args=(cc, tx_data))
    th.start()

    if DEBUG_MODE:
        frames = np.empty(0)

    if IS_PLOT:
        #グラフ表示初期化
        plot_buffer1 = np.zeros(CHUNK * PLOT_LEN)[::DOWNSAMPLE]
        plot_time = np.arange(CHUNK * PLOT_LEN)[::DOWNSAMPLE] / SAMPLING_RATE
        fig = plt.figure(num=None, figsize=(9, 6), dpi=100, facecolor='w', edgecolor='k')
        ax = plt.subplot(2, 1, 1)
        lines_sound1, = ax.plot(plot_time, plot_buffer1, color="blue", linewidth=0.5, linestyle="-", label="Sound Input")
        plt.ylim(-1, 1)
        plt.legend(loc='upper right')

        chunk_dec = int(CHUNK / cc.SEGMENT)
        plot_buffer_acc0 = np.zeros(chunk_dec * PLOT_LEN)
        plot_buffer_acc1 = np.zeros(chunk_dec * PLOT_LEN)
        plot_buffer_dec = np.zeros(chunk_dec * PLOT_LEN)
        plot_time_dec = np.arange(chunk_dec * PLOT_LEN) / SAMPLING_RATE
        ax = plt.subplot(2, 1, 2)
        lines_acc0, = ax.plot(plot_time_dec, plot_buffer_acc0, color="blue", linewidth=0.5, linestyle="-", label="Freq0 Power")
        lines_acc1, = ax.plot(plot_time_dec, plot_buffer_acc1, color="red", linewidth=0.5, linestyle="-", label="Freq1 Power")
        lines_dec, = ax.plot(plot_time_dec, plot_buffer_dec, color="green", linewidth=0.5, linestyle="-", label="dec_data")
        plt.ylim(-2, 2)
        plt.legend(loc='upper right')

        plt.tight_layout()
        #plt.show()
        plt.pause(.01)


    #メインループ
    while True:
        if cc.state == "INIT":
            cc.reset()
            cc.state = "SLEEP"
        elif cc.state == "CALIBRATION":
            if not outputstream.is_stopped:
                outputstream.stop_stream()
            if not inputstream.is_stopped:
                inputstream.stop_stream()
            inputstream.start_stream()
            init_frame = np.empty(0)
            rx_wave = rec_sound(inputstream)
            rx_wave = rec_sound(inputstream)
            for i in range(int(SAMPLING_RATE / CHUNK)):
                rx_wave = rec_sound(inputstream)
                init_frame = np.hstack((init_frame, rx_wave))
            cc.calibration(init_frame)
            inputstream.stop_stream()
            cc.state = "SLEEP"
        elif cc.state == "RX":
            if inputstream.is_stopped:
                inputstream.start_stream()
            rx_wave = rec_sound(inputstream)
            rx_result, nack_flag = cc.rx(rx_wave)

            print_rx_data(rx_result)

            if DEBUG_MODE:
                frames = np.hstack((frames, rx_wave))

            if IS_PLOT:
                acc0 = cc.acc0
                acc1 = cc.acc1
                dec_data = cc.demod
                plot_buffer1 = np.hstack([plot_buffer1[int(CHUNK / DOWNSAMPLE):int(CHUNK / DOWNSAMPLE) * PLOT_LEN], rx_wave[::DOWNSAMPLE]])
                lines_sound1.set_data(plot_time , plot_buffer1)
                plot_buffer_acc0 = np.hstack([plot_buffer_acc0[chunk_dec:chunk_dec * PLOT_LEN], acc0])
                lines_acc0.set_data(plot_time_dec , plot_buffer_acc0)
                plot_buffer_acc1 = np.hstack([plot_buffer_acc1[chunk_dec:chunk_dec * PLOT_LEN], acc1])
                lines_acc1.set_data(plot_time_dec , plot_buffer_acc1)
                plot_buffer_dec = np.hstack([plot_buffer_dec[chunk_dec:chunk_dec * PLOT_LEN], dec_data])
                lines_dec.set_data(plot_time_dec , plot_buffer_dec)
                fig.canvas.draw()
                fig.canvas.flush_events()

            if len(rx_result) > 0:
                if nack_flag:
                    cc.state = "TX_NACK"
                else:
                    cc.state = "TX_ACK"
            else:
                cc.state = cc.state
        elif cc.state == "TX_ACK":
            if not inputstream.is_stopped:
                inputstream.stop_stream()
            if outputstream.is_stopped:
                outputstream.start_stream()
            tx_wave = cc.tx_acknack([1, 1])
            time.sleep(0.5)
            play_sound(outputstream, tx_wave)
            time.sleep(0.2)
            cc.state = "RX"
        elif cc.state == "TX_NACK":
            if not inputstream.is_stopped:
                inputstream.stop_stream()
            if outputstream.is_stopped:
                outputstream.start_stream()
            tx_wave = cc.tx_acknack([0, 0])
            time.sleep(0.5)
            play_sound(outputstream, tx_wave)
            time.sleep(0.2)
            cc.state = "RX"
        elif cc.state == "TX":
            print("TX")
            if not inputstream.is_stopped:
                inputstream.stop_stream()
            if outputstream.is_stopped:
                outputstream.start_stream()
            tx_wave = cc.tx(tx_data)
            time.sleep(0.5)
            play_sound(outputstream, tx_wave)
            time.sleep(0.2)
            print("WAIT_ACKNACK")
            cc.state = "WAIT_ACKNACK"
            #cc.state = "SLEEP"
        elif cc.state == "WAIT_ACKNACK":
            if inputstream.is_stopped:
                inputstream.start_stream()
            rx_wave = rec_sound(inputstream)
            rx_result, nack_flag = cc.rx_acknack(rx_wave)

            print_rx_data(rx_result)

            if DEBUG_MODE:
                frames = np.hstack((frames, rx_wave))

            if IS_PLOT:
                acc0 = cc.acc0
                acc1 = cc.acc1
                dec_data = cc.demod
                plot_buffer1 = np.hstack([plot_buffer1[int(CHUNK / DOWNSAMPLE):int(CHUNK / DOWNSAMPLE) * PLOT_LEN], rx_wave[::DOWNSAMPLE]])
                lines_sound1.set_data(plot_time , plot_buffer1)
                plot_buffer_acc0 = np.hstack([plot_buffer_acc0[chunk_dec:chunk_dec * PLOT_LEN], acc0])
                lines_acc0.set_data(plot_time_dec , plot_buffer_acc0)
                plot_buffer_acc1 = np.hstack([plot_buffer_acc1[chunk_dec:chunk_dec * PLOT_LEN], acc1])
                lines_acc1.set_data(plot_time_dec , plot_buffer_acc1)
                plot_buffer_dec = np.hstack([plot_buffer_dec[chunk_dec:chunk_dec * PLOT_LEN], dec_data])
                lines_dec.set_data(plot_time_dec , plot_buffer_dec)
                fig.canvas.draw()
                fig.canvas.flush_events()

            if len(rx_result) > 0:
                if nack_flag:
                    print("NACK_RECEIVED")
                else:
                    print("ACK_RECEIVED")
                cc.state = "RX"
            else:
                cc.state = cc.state
        elif cc.state == "SLEEP":
            if not inputstream.is_stopped:
                inputstream.stop_stream()
            time.sleep(0.5)
        elif cc.state == "EXIT":
            # スピーカーとマイクの終了処理
            pyaudio_finish(paudio, inputstream, outputstream)
            # メインループを抜ける
            break

    print("done.")

    if DEBUG_MODE:
        plt.figure(num=None, figsize=(8, 6), dpi=150, facecolor='w', edgecolor='k')
        ax = plt.subplot(1, 1, 1)
        plt.plot(frames, color="blue", linewidth=1.5, linestyle="-", label="rx")
        plt.show()

        output_psd_fp = open("result_rec.csv", 'w')
        for idx, data in enumerate(frames):
            output_psd_fp.write(str(idx))
            output_psd_fp.write(",")
            output_psd_fp.write(str(data))
            output_psd_fp.write("\n")
        output_psd_fp.close()
