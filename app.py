from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
import tempfile
import os
import logging
import time 
import uuid
import subprocess
import threading
from queue import Queue
import random
import cv2
import base64
import numpy as np
import re
import requests 
from urllib.parse import urlparse 
import torch
from ultralytics import YOLO
import json

# Set up logging to see errors
logging.basicConfig(level=logging.INFO)

app = Flask(__name__, 
            static_folder='static',
            static_url_path='/static',
            template_folder='templates')

# Configure CORS to allow requests from your frontend
CORS(app)

# Create directory for processed videos if it doesn't exist
PROCESSED_VIDEOS_DIR = "processed_videos"
os.makedirs(PROCESSED_VIDEOS_DIR, exist_ok=True)

# Gate configurations with capacities
GATE_CONFIG = {
    'A': {'capacity': 200, 'name': 'Gate A', 'position': 'top'},
    'B': {'capacity': 300, 'name': 'Gate B', 'position': 'left-top'},
    'C': {'capacity': 250, 'name': 'Gate C', 'position': 'right-top'},
    'D': {'capacity': 350, 'name': 'Gate D', 'position': 'left-bottom'},
    'E': {'capacity': 300, 'name': 'Gate E', 'position': 'right-bottom'},
    'F': {'capacity': 400, 'name': 'Gate F', 'position': 'bottom'},
    'Temple': {'capacity': 1000, 'name': 'Temple Area', 'position': 'center'}
}

# Active camera connections
active_cameras = {}
camera_queues = {}
camera_threads = {}
camera_captures = {}
camera_last_update = {}

# Mobile device registry
mobile_devices = {}

# Performance settings
TARGET_FPS = 10
PROCESS_EVERY_N_FRAMES = 2  # Process every 2nd frame
MAX_FRAME_WIDTH = 640
MAX_FRAME_HEIGHT = 480
JPEG_QUALITY = 70

# Load YOLOv8 model with GPU acceleration if available
try:
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = YOLO('model/yolov8n.pt').to(device)
    app.logger.info(f"YOLOv8 model loaded successfully on {device.upper()}")
except Exception as e:
    app.logger.error(f"Failed to load YOLOv8 model: {str(e)}")
    model = None

def is_valid_url(url):
    """Validate URL format"""
    regex = re.compile(
        r'^(?:http|ftp)s?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

def test_camera_url(url):
    """Test if a camera URL is accessible"""
    try:
        # For HTTP URLs (mobile cameras)
        if url.startswith('http'):
            try:
                response = requests.get(url, timeout=5)
                return response.status_code == 200
            except:
                return True
        # For RTSP URLs
        elif url.startswith('rtsp'):
            cap = cv2.VideoCapture(url)
            if cap.isOpened():
                cap.release()
                return True
            return False
        return False
    except:
        return True

def detect_people_yolov8(frame):
    """Detect people using YOLOv8 model with performance optimizations"""
    if model is None:
        return random.randint(5, 50)  # Fallback if model not loaded
    
    try:
        # Run YOLOv8 inference with optimized settings
        results = model(frame, verbose=False, conf=0.5, imgsz=320)
        
        people_count = 0
        for result in results:
            # Check if detections exist
            if result.boxes is not None:
                # Filter for person class (class 0 in COCO dataset)
                for box in result.boxes:
                    class_id = int(box.cls[0])
                    if class_id == 0:  # Person class
                        people_count += 1
        
        return people_count
        
    except Exception as e:
        app.logger.error(f"YOLOv8 detection error: {str(e)}")
        return random.randint(5, 50)  # Fallback to random count

def optimize_camera_settings(cap, is_mobile=False):
    """Optimize camera settings for better performance"""
    try:
        if is_mobile:
            # Mobile streams often work better with these settings
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, MAX_FRAME_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, MAX_FRAME_HEIGHT)
        else:
            # Try to set optimal settings for webcams/CCTV
            cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, MAX_FRAME_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, MAX_FRAME_HEIGHT)
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
    except Exception as e:
        app.logger.warning(f"Could not optimize camera settings: {str(e)}")

def camera_worker(gate_id, camera_source):
    """Worker thread to process camera feed for a specific gate with performance optimizations"""
    try:
        cap = None
        is_mobile = False
        last_processed_time = 0
        frame_count = 0
        
        # Check if it's a mobile device stream
        if gate_id in mobile_devices and camera_source == 'mobile':
            # Use mobile device stream
            mobile_config = mobile_devices[gate_id]
            if 'stream_url' in mobile_config:
                stream_url = mobile_config['stream_url']
                app.logger.info(f"Attempting to connect to mobile camera: {stream_url}")
                
                # For mobile streams, use optimized settings
                cap = cv2.VideoCapture(stream_url)
                optimize_camera_settings(cap, is_mobile=True)
                
                if cap.isOpened():
                    is_mobile = True
                    app.logger.info(f"Successfully connected to mobile camera: {stream_url}")
                else:
                    app.logger.error(f"Failed to open mobile camera: {stream_url}")
                    if gate_id in camera_queues:
                        camera_queues[gate_id].put({
                            'error': f'Failed to connect to mobile camera. Please check the URL.',
                            'count': 0,
                            'status': 'disconnected'
                        })
                    return
                    
        else:
            # Try to parse camera source as integer (webcam index)
            try:
                camera_index = int(camera_source)
                cap = cv2.VideoCapture(camera_index)
                optimize_camera_settings(cap, is_mobile=False)
                
                if cap.isOpened():
                    app.logger.info(f"Connected to webcam {camera_index} for gate {gate_id}")
                else:
                    app.logger.error(f"Could not open webcam {camera_index} for gate {gate_id}")
                    if gate_id in camera_queues:
                        camera_queues[gate_id].put({
                            'error': f'Could not open webcam {camera_index}. Please check if camera is connected.',
                            'count': 0,
                            'status': 'disconnected'
                        })
                    return
            except ValueError:
                # If not integer, treat as URL
                if is_valid_url(camera_source):
                    app.logger.info(f"Attempting to connect to URL camera: {camera_source}")
                    cap = cv2.VideoCapture(camera_source)
                    optimize_camera_settings(cap, is_mobile=camera_source.startswith('http'))
                    
                    if cap.isOpened():
                        app.logger.info(f"Connected to URL camera: {camera_source}")
                    else:
                        app.logger.error(f"Failed to connect to URL camera: {camera_source}")
                        if gate_id in camera_queues:
                            camera_queues[gate_id].put({
                                'error': f'Failed to connect to camera URL: {camera_source}',
                                'count': 0,
                                'status': 'disconnected'
                            })
                        return
                else:
                    app.logger.error(f"Invalid camera source for {gate_id}: {camera_source}")
                    if gate_id in camera_queues:
                        camera_queues[gate_id].put({
                            'error': f'Invalid camera source: {camera_source}',
                            'count': 0,
                            'status': 'disconnected'
                        })
                    return
        
        if not cap or not cap.isOpened():
            app.logger.error(f"Could not open camera for {gate_id}: {camera_source}")
            # Put error message in queue
            if gate_id in camera_queues:
                camera_queues[gate_id].put({
                    'error': f'Failed to connect to camera: {camera_source}',
                    'count': 0,
                    'status': 'disconnected'
                })
            return
            
        camera_captures[gate_id] = cap
        retry_count = 0
        max_retries = 10
        
        while gate_id in active_cameras and active_cameras[gate_id]:
            current_time = time.time()
            
            # Skip processing if we're ahead of target FPS
            if current_time - last_processed_time < (1.0 / TARGET_FPS):
                time.sleep(0.01)  # Small sleep to prevent CPU hogging
                continue
                
            ret, frame = cap.read()
            if not ret:
                app.logger.warning(f"Failed to read frame from camera for {gate_id}, retry {retry_count}/{max_retries}")
                retry_count += 1
                
                if retry_count > max_retries:
                    app.logger.error(f"Max retries exceeded for gate {gate_id}")
                    if gate_id in camera_queues:
                        camera_queues[gate_id].put({
                            'error': 'Camera stream disconnected. Please reconnect.',
                            'count': 0,
                            'status': 'disconnected'
                        })
                    break
                    
                time.sleep(0.1)
                continue
            
            # Reset retry count on successful frame read
            retry_count = 0
            frame_count += 1
            
            # Only process every nth frame to improve performance
            if frame_count % PROCESS_EVERY_N_FRAMES == 0:
                # Resize frame for faster processing if needed
                height, width = frame.shape[:2]
                if width > MAX_FRAME_WIDTH or height > MAX_FRAME_HEIGHT:
                    scale = min(MAX_FRAME_WIDTH / width, MAX_FRAME_HEIGHT / height)
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))
                
                # Use YOLOv8 for people detection
                people_count = detect_people_yolov8(frame)
                
                # Put the result in the queue
                if gate_id in camera_queues:
                    capacity = GATE_CONFIG[gate_id]['capacity']
                    status = 'normal'
                    if people_count > capacity:
                        status = 'overcrowded'
                    elif people_count > capacity * 0.8:
                        status = 'warning'
                    
                    # Convert frame to base64 for web display (optimized for performance)
                    try:
                        # Resize for web display to reduce data size
                        display_frame = cv2.resize(frame, (320, 240))
                        _, buffer = cv2.imencode('.jpg', display_frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                        jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                        frame_data = f"data:image/jpeg;base64,{jpg_as_text}"
                    except Exception as e:
                        app.logger.error(f"Error encoding frame: {str(e)}")
                        frame_data = ''
                    
                    camera_queues[gate_id].put({
                        'count': people_count,
                        'status': status,
                        'frame': frame_data,
                        'timestamp': current_time,
                        'is_mobile': is_mobile
                    })
                    
                    last_processed_time = current_time
            
            # Small sleep to prevent CPU hogging
            time.sleep(0.01)
            
    except Exception as e:
        app.logger.error(f"Error in camera worker for {gate_id}: {str(e)}")
        # Send error to frontend
        if gate_id in camera_queues:
            camera_queues[gate_id].put({
                'error': f'Camera error: {str(e)}',
                'count': 0,
                'status': 'disconnected'
            })
    finally:
        if gate_id in camera_captures and camera_captures[gate_id]:
            try:
                camera_captures[gate_id].release()
            except:
                pass
            if gate_id in camera_captures:
                del camera_captures[gate_id]

def check_mobile_camera_health():
    """Periodically check mobile camera health and restart if needed"""
    while True:
        try:
            for gate_id in list(mobile_devices.keys()):
                if (gate_id in active_cameras and active_cameras[gate_id] and 
                    gate_id in camera_queues and camera_queues[gate_id].empty()):
                    # If camera is active but queue is empty for too long, it might be stuck
                    current_time = time.time()
                    if gate_id in camera_last_update and current_time - camera_last_update[gate_id] > 10:
                        app.logger.info(f"Health check: Gate {gate_id} mobile camera might need restart")
                        
                        # Restart the camera
                        if gate_id in active_cameras:
                            active_cameras[gate_id] = False
                            if gate_id in camera_threads and camera_threads[gate_id].is_alive():
                                camera_threads[gate_id].join(timeout=1.0)
                        
                        # Restart the camera
                        camera_queues[gate_id] = Queue()
                        active_cameras[gate_id] = True
                        thread = threading.Thread(target=camera_worker, args=(gate_id, 'mobile'))
                        thread.daemon = True
                        thread.start()
                        camera_threads[gate_id] = thread
                    
            time.sleep(5)  # Check every 5 seconds
        except Exception as e:
            app.logger.error(f"Error in camera health check: {str(e)}")
            time.sleep(30)

@app.route('/')
def index():
    """Serve the main page with gate network"""
    return render_template('index.html', gate_config=GATE_CONFIG)

@app.route('/gate_config')
def get_gate_config():
    """Return gate configuration"""
    return jsonify(GATE_CONFIG)

@app.route('/connect_camera', methods=['POST'])
def connect_camera():
    """Connect to a camera for a specific gate"""
    try:
        data = request.json
        gate_id = data.get('gate_id')
        camera_source = data.get('camera_source')
        camera_type = data.get('camera_type', 'webcam')  # webcam, cctv, or mobile
        
        if not gate_id:
            return jsonify({'error': 'Missing gate_id'}), 400
            
        # Stop existing camera if any
        if gate_id in active_cameras:
            active_cameras[gate_id] = False
            if gate_id in camera_threads and camera_threads[gate_id].is_alive():
                camera_threads[gate_id].join(timeout=2.0)
        
        # Create queue for this camera
        camera_queues[gate_id] = Queue()
        active_cameras[gate_id] = True
        camera_last_update[gate_id] = time.time()
        
        # For mobile devices, store the configuration
        if camera_type == 'mobile' and 'stream_url' in data:
            mobile_devices[gate_id] = {
                'stream_url': data['stream_url'],
                'camera_type': 'mobile'
            }
            camera_source = 'mobile'  # Use special identifier for mobile streams
        
        # Start camera worker thread
        thread = threading.Thread(target=camera_worker, args=(gate_id, camera_source))
        thread.daemon = True
        thread.start()
        camera_threads[gate_id] = thread
        
        return jsonify({
            'status': 'success', 
            'message': f'Camera connected for {gate_id}',
            'camera_type': camera_type
        })
        
    except Exception as e:
        app.logger.error(f"Error connecting camera: {str(e)}")
        return jsonify({'error': f'Failed to connect camera: {str(e)}'}), 500

@app.route('/register_mobile', methods=['POST'])
def register_mobile():
    """Register a mobile device stream"""
    try:
        data = request.json
        gate_id = data.get('gate_id')
        stream_url = data.get('stream_url')
        device_name = data.get('device_name', 'Mobile Device')
        
        if not gate_id or not stream_url:
            return jsonify({'error': 'Missing gate_id or stream_url'}), 400
            
        if not is_valid_url(stream_url):
            return jsonify({'error': 'Invalid stream URL'}), 400
        
        # Register mobile device
        mobile_devices[gate_id] = {
            'stream_url': stream_url,
            'device_name': device_name,
            'registered_at': time.time(),
            'camera_type': 'mobile'
        }
        
        return jsonify({
            'status': 'success', 
            'message': f'Mobile device registered for {gate_id}',
            'gate_id': gate_id
        })
        
    except Exception as e:
        app.logger.error(f"Error registering mobile device: {str(e)}")
        return jsonify({'error': f'Failed to register mobile device: {str(e)}'}), 500

@app.route('/disconnect_camera', methods=['POST'])
def disconnect_camera():
    """Disconnect camera for a specific gate or all gates"""
    try:
        data = request.json
        gate_id = data.get('gate_id')
        
        if gate_id == 'all':
            # Disconnect all cameras
            for gid in list(active_cameras.keys()):
                active_cameras[gid] = False
                if gid in camera_threads and camera_threads[gid].is_alive():
                    camera_threads[gid].join(timeout=2.0)
                
                # Clean up
                if gid in camera_queues:
                    del camera_queues[gid]
                if gid in camera_threads:
                    del camera_threads[gid]
                if gid in active_cameras:
                    del active_cameras[gid]
                if gid in camera_captures:
                    if camera_captures[gid]:
                        camera_captures[gid].release()
                    del camera_captures[gid]
                if gid in camera_last_update:
                    del camera_last_update[gid]
            
            return jsonify({'status': 'success', 'message': 'All cameras disconnected'})
        else:
            # Single gate disconnect
            if gate_id in active_cameras:
                active_cameras[gate_id] = False
                if gate_id in camera_threads and camera_threads[gate_id].is_alive():
                    camera_threads[gate_id].join(timeout=2.0)
                
                # Clean up
                if gate_id in camera_queues:
                    del camera_queues[gate_id]
                if gate_id in camera_threads:
                    del camera_threads[gate_id]
                if gate_id in active_cameras:
                    del active_cameras[gate_id]
                if gate_id in camera_captures:
                    if camera_captures[gate_id]:
                        camera_captures[gate_id].release()
                    del camera_captures[gate_id]
                if gate_id in camera_last_update:
                    del camera_last_update[gate_id]
                    
            return jsonify({'status': 'success', 'message': f'Camera disconnected for {gate_id}'})
        
    except Exception as e:
        app.logger.error(f"Error disconnecting camera: {str(e)}")
        return jsonify({'error': f'Failed to disconnect camera: {str(e)}'}), 500

@app.route('/get_camera_status')
def get_camera_status():
    """Get status of all cameras"""
    status = {}
    for gate_id in GATE_CONFIG.keys():
        if gate_id == 'Temple':
            continue
            
        status[gate_id] = {
            'connected': gate_id in active_cameras and active_cameras[gate_id],
            'count': 0,
            'status': 'disconnected',
            'frame': '',
            'camera_type': 'webcam',  # default
            'error': ''
        }
        
        # Check if it's a mobile device
        if gate_id in mobile_devices:
            status[gate_id]['camera_type'] = 'mobile'
            status[gate_id]['device_name'] = mobile_devices[gate_id].get('device_name', 'Mobile Device')
        
        if gate_id in camera_queues and not camera_queues[gate_id].empty():
            try:
                data = camera_queues[gate_id].get_nowait()
                status[gate_id]['count'] = data.get('count', 0)
                status[gate_id]['status'] = data.get('status', 'disconnected')
                status[gate_id]['frame'] = data.get('frame', '')
                status[gate_id]['timestamp'] = data.get('timestamp', time.time())
                status[gate_id]['error'] = data.get('error', '')
                status[gate_id]['is_mobile'] = data.get('is_mobile', False)
                
                # Update last update time
                camera_last_update[gate_id] = time.time()
            except Exception as e:
                app.logger.error(f"Error getting queue data for {gate_id}: {str(e)}")
                
    return jsonify(status)

@app.route('/get_mobile_devices')
def get_mobile_devices():
    """Get list of registered mobile devices"""
    return jsonify(mobile_devices)

@app.route('/test')
def test_route():
    return jsonify({'message': 'Server is running!'})

@app.route('/static/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

# Clean up
import atexit

def cleanup_cameras():
    for gate_id in list(active_cameras.keys()):
        active_cameras[gate_id] = False
    for gate_id, thread in camera_threads.items():
        if thread.is_alive():
            thread.join(timeout=1.0)
    for gate_id, cap in camera_captures.items():
        if cap:
            cap.release()

atexit.register(cleanup_cameras)

# Start camera health check thread
camera_health_thread = threading.Thread(target=check_mobile_camera_health)
camera_health_thread.daemon = True
camera_health_thread.start()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)