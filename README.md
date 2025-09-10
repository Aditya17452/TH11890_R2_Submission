# 🚩 Ujjain Kumbh Crowd Management System

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![OpenCV](https://img.shields.io/badge/OpenCV-4.9-orange)
![Flask](https://img.shields.io/badge/Flask-2.3-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

**AI-powered crowd management system for mass gatherings with real-time gate monitoring and automatic alert system**

## 🌟 Overview

Smart temple crowd management system that uses computer vision to monitor six gates in real-time, detects overcrowding using AI algorithms, and automatically alerts authorities when safety thresholds are breached. Specifically designed for religious mass gatherings like Kumbh Mela to prevent dangerous crowd situations.

> **"सुरक्षित प्रवाह, सुरक्षित लोग"** *(Safe Flow, Safe People)*

## 🚀 Features

- **Real-time Monitoring**: Live camera feeds from all six gates
- **AI People Counting**: Computer vision-based crowd density analysis
- **Automatic Alerts**: Instant notifications when capacity thresholds exceeded
- **Multi-Camera Support**: Webcam, mobile, and CCTV integration
- **Color-coded Dashboard**: Visual status indicators (Green/Yellow/Red)
- **Authority Notifications**: SMS/dashboard alerts for emergency response

## 🛠️ Installation

```bash
# Clone the repository
git clone https://github.com/your-username/ujjain-crowd-management.git

# Navigate to project directory
cd ujjain-crowd-management

# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py