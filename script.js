// Global variables
let currentGate = null;
let statusInterval = null;

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    startStatusUpdates();
    testServerConnection();
});

// Handle camera selection from dropdown
function handleCameraSelect(selectElement) {
    const gateId = selectElement.dataset.gate;
    const sourceType = selectElement.value;
    
    if (!sourceType) return;
    
    if (sourceType === 'mobile') {
        showMobileModal(gateId);
    } else if (sourceType === 'url') {
        showCameraModal(gateId);
    } else {
        // Regular webcam connection
        connectWebcam(gateId, sourceType);
    }
    
    // Reset the selection
    selectElement.value = "";
}

// Initialize event listeners
function initializeEventListeners() {
    // Camera source change
    document.getElementById('cameraSource').addEventListener('change', function() {
        document.getElementById('urlInputGroup').style.display = this.value === 'url' ? 'block' : 'none';
    });
    
    // Modal buttons
    document.getElementById('connectCameraBtn').addEventListener('click', connectCamera);
    document.getElementById('cancelCameraBtn').addEventListener('click', hideCameraModal);
    
    // Mobile modal buttons
    document.getElementById('registerMobileBtn').addEventListener('click', registerMobileDevice);
    document.getElementById('cancelMobileBtn').addEventListener('click', hideMobileModal);
    
    // Control buttons
    document.getElementById('refreshBtn').addEventListener('click', refreshStatus);
    document.getElementById('resetBtn').addEventListener('click', disconnectAllCameras);
}

// Show camera modal
function showCameraModal(gateId) {
    currentGate = gateId;
    document.getElementById('modalGateId').textContent = `Gate ${gateId}`;
    document.getElementById('cameraModal').style.display = 'block';
    document.getElementById('cameraSource').value = '0';
    document.getElementById('cctvUrl').value = '';
    document.getElementById('urlInputGroup').style.display = 'none';
}

// Hide camera modal
function hideCameraModal() {
    document.getElementById('cameraModal').style.display = 'none';
    currentGate = null;
}

// Show mobile modal
function showMobileModal(gateId) {
    currentGate = gateId;
    document.getElementById('mobileModal').style.display = 'block';
    document.getElementById('mobileGateId').textContent = `Gate ${gateId}`;
    document.getElementById('mobileStreamUrl').value = '';
    document.getElementById('mobileDeviceName').value = `Mobile Camera ${gateId}`;
}

// Hide mobile modal
function hideMobileModal() {
    document.getElementById('mobileModal').style.display = 'none';
    currentGate = null;
}

// Connect webcam directly
function connectWebcam(gateId, cameraSource) {
    showLoading();
    
    fetch('/connect_camera', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            gate_id: gateId,
            camera_source: cameraSource,
            camera_type: 'webcam'
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert(`Camera connected for Gate ${gateId}`);
            refreshStatus();
        } else {
            alert(`Error: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Error connecting camera:', error);
        alert('Failed to connect camera');
    })
    .finally(() => {
        hideLoading();
    });
}

// Connect camera from modal
function connectCamera() {
    const source = document.getElementById('cameraSource').value;
    let cameraSource = source;
    
    if (source === 'url') {
        cameraSource = document.getElementById('cctvUrl').value;
        if (!cameraSource) {
            alert('Please enter a valid CCTV URL');
            return;
        }
    }
    
    showLoading();
    
    fetch('/connect_camera', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            gate_id: currentGate,
            camera_source: cameraSource,
            camera_type: source === 'url' ? 'cctv' : 'webcam'
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert(`Camera connected successfully for Gate ${currentGate}`);
            hideCameraModal();
            refreshStatus();
        } else {
            alert(`Error: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Error connecting camera:', error);
        alert('Failed to connect camera. Please check if the server is running.');
    })
    .finally(() => {
        hideLoading();
    });
}

// Register mobile device
function registerMobileDevice() {
    const gateId = currentGate;
    const streamUrl = document.getElementById('mobileStreamUrl').value;
    const deviceName = document.getElementById('mobileDeviceName').value || `Mobile Camera ${gateId}`;
    
    if (!streamUrl) {
        alert('Please enter a valid stream URL');
        return;
    }
    
    if (!streamUrl.startsWith('http://') && !streamUrl.startsWith('https://') && !streamUrl.startsWith('rtsp://')) {
        alert('Please enter a valid URL starting with http://, https://, or rtsp://');
        return;
    }
    
    showLoading();
    
    fetch('/register_mobile', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            gate_id: gateId,
            stream_url: streamUrl,
            device_name: deviceName
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert(`Mobile device registered for Gate ${gateId}`);
            hideMobileModal();
            connectMobileCamera(gateId);
        } else {
            alert(`Error: ${data.error || 'Failed to register mobile device'}`);
        }
    })
    .catch(error => {
        console.error('Error registering mobile device:', error);
        alert('Failed to register mobile device. Please check if the server is running.');
    })
    .finally(() => {
        hideLoading();
    });
}

// Connect mobile camera
function connectMobileCamera(gateId) {
    showLoading();
    
    fetch('/connect_camera', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            gate_id: gateId,
            camera_source: 'mobile',
            camera_type: 'mobile'
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert(`Mobile camera connected for Gate ${gateId}`);
            refreshStatus();
        } else {
            alert(`Error: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Error connecting mobile camera:', error);
        alert('Failed to connect mobile camera');
    })
    .finally(() => {
        hideLoading();
    });
}

// Refresh status
async function refreshStatus() {
    try {
        const response = await fetch('/get_camera_status');
        const status = await response.json();
        
        updateStatusDisplay(status);
        updateCameraFeeds(status);
        updateAlertPanel(status);
    } catch (error) {
        console.error('Error refreshing status:', error);
    }
}

// Update status display
function updateStatusDisplay(status) {
    Object.entries(status).forEach(([gateId, gateStatus]) => {
        const statusElement = document.querySelector(`.status-item[data-gate="${gateId}"]`);
        const countElement = document.querySelector(`.count-item[data-gate="${gateId}"] span`);
        
        if (statusElement && countElement) {
            // Update status indicator
            statusElement.innerHTML = `<span class="status-indicator"></span> Gate ${gateId}: `;
            const indicator = statusElement.querySelector('.status-indicator');
            
            if (gateStatus.connected) {
                if (gateStatus.status === 'overcrowded') {
                    indicator.classList.add('status-danger');
                    statusElement.innerHTML += 'OVERCROWDED';
                } else if (gateStatus.status === 'warning') {
                    indicator.classList.add('status-warning');
                    statusElement.innerHTML += 'WARNING';
                } else {
                    indicator.classList.add('status-connected');
                    statusElement.innerHTML += 'Connected';
                    
                    // Add camera type info
                    if (gateStatus.camera_type === 'mobile') {
                        statusElement.innerHTML += ' (Mobile)';
                    } else {
                        statusElement.innerHTML += ' (Webcam)';
                    }
                }
            } else {
                indicator.classList.add('status-disconnected');
                statusElement.innerHTML += 'Disconnected';
                
                // Show error if exists
                if (gateStatus.error) {
                    statusElement.innerHTML += ` - ${gateStatus.error}`;
                }
            }
            
            // Update count
            countElement.textContent = gateStatus.count;
            
            // Update gate visual appearance
            const gateElement = document.querySelector(`.gate[data-gate="${gateId}"]`);
            if (gateElement) {
                gateElement.classList.remove('gate-overcrowded', 'gate-warning');
                
                if (gateStatus.status === 'overcrowded') {
                    gateElement.classList.add('gate-overcrowded');
                } else if (gateStatus.status === 'warning') {
                    gateElement.classList.add('gate-warning');
                }
            }
        }
    });
}

// Update camera feeds
function updateCameraFeeds(status) {
    // Clear error messages for gates that are now connected
    document.querySelectorAll('.camera-error').forEach(errorDiv => {
        const gateId = errorDiv.dataset.gate;
        if (status[gateId] && status[gateId].connected && !status[gateId].error) {
            errorDiv.remove();
        }
    });
    
    // Clear only feeds that are no longer connected
    document.querySelectorAll('.camera-feed').forEach(feed => {
        const gateId = feed.dataset.gate;
        if (!status[gateId] || !status[gateId].connected) {
            feed.remove();
        }
    });
    
    // Create feed for each connected camera
    Object.entries(status).forEach(([gateId, gateStatus]) => {
        if (gateStatus.error) {
            // Show error message
            handleCameraError(gateId, gateStatus.error);
        } else if (gateStatus.connected) {
            // Check if feed already exists
            let feedDiv = document.querySelector(`.camera-feed[data-gate="${gateId}"]`);
            
            if (!feedDiv) {
                // Create new feed
                feedDiv = document.createElement('div');
                feedDiv.className = 'camera-feed';
                feedDiv.dataset.gate = gateId;
                document.getElementById('cameraFeeds').appendChild(feedDiv);
            }
            
            if (gateStatus.frame) {
                // Update feed content with live frame
                feedDiv.innerHTML = `
                    <h4>Gate ${gateId} Live Feed ${gateStatus.is_mobile ? '(Mobile)' : ''}</h4>
                    <img src="${gateStatus.frame}" alt="Gate ${gateId} Camera Feed" 
                         onerror="this.style.display='none'; this.nextElementSibling.style.display='block'">
                    <div class="feed-error" style="display: none;">
                        Failed to load image. The stream may be unavailable.
                    </div>
                    <div class="feed-count">Count: ${gateStatus.count}/${getCapacityForGate(gateId)}</div>
                `;
            } else {
                // Show placeholder when no frame is available
                feedDiv.innerHTML = `
                    <h4>Gate ${gateId} Live Feed ${gateStatus.is_mobile ? '(Mobile)' : ''}</h4>
                    <div style="width: 320px; height: 240px; background: #ccc; display: flex; align-items: center; justify-content: center;">
                        <span>Waiting for video stream...</span>
                    </div>
                    <div class="feed-count">Count: ${gateStatus.count}/${getCapacityForGate(gateId)}</div>
                `;
            }
        }
    });
}

// Handle camera error
function handleCameraError(gateId, errorMessage) {
    const statusElement = document.querySelector(`.status-item[data-gate="${gateId}"]`);
    if (statusElement) {
        statusElement.innerHTML = `<span class="status-indicator status-disconnected"></span> Gate ${gateId}: Error - ${errorMessage}`;
    }
    
    // Remove any existing feed for this gate
    const existingFeed = document.querySelector(`.camera-feed[data-gate="${gateId}"]`);
    if (existingFeed) {
        existingFeed.remove();
    }
    
    // Show error in the camera feeds section
    let errorDiv = document.querySelector(`.camera-error[data-gate="${gateId}"]`);
    if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'camera-error';
        errorDiv.dataset.gate = gateId;
        document.getElementById('cameraFeeds').appendChild(errorDiv);
    }
    errorDiv.innerHTML = `<strong>Gate ${gateId} Error:</strong> ${errorMessage}`;
}

// Update alert panel
function updateAlertPanel(status) {
    const alertList = document.getElementById('alertList');
    alertList.innerHTML = '';
    
    let hasAlerts = false;
    
    Object.entries(status).forEach(([gateId, gateStatus]) => {
        if (gateStatus.status === 'overcrowded') {
            hasAlerts = true;
            const li = document.createElement('li');
            li.textContent = `Gate ${gateId} is OVERCROWDED! Count: ${gateStatus.count}/${getCapacityForGate(gateId)}`;
            alertList.appendChild(li);
        } else if (gateStatus.status === 'warning') {
            hasAlerts = true;
            const li = document.createElement('li');
            li.textContent = `Gate ${gateId} is nearing capacity. Count: ${gateStatus.count}/${getCapacityForGate(gateId)}`;
            alertList.appendChild(li);
        }
    });
    
    // Show/hide alert panel
    document.getElementById('alertPanel').style.display = hasAlerts ? 'block' : 'none';
}

// Get capacity for gate
function getCapacityForGate(gateId) {
    const capacities = {
        'A': 200,
        'B': 300, 
        'C': 250,
        'D': 350,
        'E': 300,
        'F': 400
    };
    return capacities[gateId] || 0;
}

// Disconnect all cameras
function disconnectAllCameras() {
    showLoading();
    
    fetch('/disconnect_camera', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            gate_id: 'all'
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            alert('All cameras disconnected');
            refreshStatus();
        } else {
            alert(`Error: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Error disconnecting cameras:', error);
        alert('Failed to disconnect cameras');
    })
    .finally(() => {
        hideLoading();
    });
}

// Start status updates
function startStatusUpdates() {
    // Refresh status every 2 seconds
    statusInterval = setInterval(refreshStatus, 400);
    refreshStatus(); // Initial refresh
}

// Stop status updates
function stopStatusUpdates() {
    if (statusInterval) {
        clearInterval(statusInterval);
    }
}

// Show loading overlay
function showLoading() {
    document.getElementById('loadingOverlay').style.display = 'flex';
}

// Hide loading overlay
function hideLoading() {
    document.getElementById('loadingOverlay').style.display = 'none';
}

// Test server connection
async function testServerConnection() {
    try {
        const response = await fetch('/test');
        if (response.ok) {
            console.log('✅ Server connection successful');
        } else {
            console.warn('⚠️ Server responded with error status');
        }
    } catch (error) {
        console.warn('❌ Could not connect to server');
    }
}

// Clean up on page unload
window.addEventListener('beforeunload', stopStatusUpdates);

// Initialize Crowd Popup
function initCrowdPopup() {
    const crowdPopup = document.getElementById('crowd-popup');
    const closePopupBtn = document.getElementById('close-crowd-popup');
    const startSystemBtn = document.getElementById('start-system-btn');
    
    // Show the popup when page loads
    crowdPopup.style.display = 'flex';
    document.body.classList.add('crowd-popup-visible');
    
    // Close popup when clicking close button
    closePopupBtn.addEventListener('click', closeCrowdPopup);
    
    // Close popup when clicking start button
    startSystemBtn.addEventListener('click', closeCrowdPopup);
    
    // Close popup when clicking outside content
    crowdPopup.addEventListener('click', function(e) {
        if (e.target === crowdPopup) {
            closeCrowdPopup();
        }
    });
    
    // Close popup with Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && crowdPopup.style.display === 'flex') {
            closeCrowdPopup();
        }
    });
}

// Close crowd popup
function closeCrowdPopup() {
    const crowdPopup = document.getElementById('crowd-popup');
    crowdPopup.style.display = 'none';
    document.body.classList.remove('crowd-popup-visible');
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize the crowd popup
    initCrowdPopup();
    
    // Your other initialization code...
    initLiveStream();
    loadModel();
    initHeatmap();
    initMobileCamera();
});