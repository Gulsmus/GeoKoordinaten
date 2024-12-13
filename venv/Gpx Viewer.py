from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import gpxpy
import gpxpy.gpx
import math
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gpx_data.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database models
class Track(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    file_path = db.Column(db.String(200), nullable=False)
    vehicle = db.Column(db.String(100), nullable=True)
    driver = db.Column(db.String(100), nullable=True)
    date = db.Column(db.Date, nullable=True)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    coordinates = db.relationship('Coordinate', backref='track', lazy=True)

class Coordinate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    speed = db.Column(db.Float, nullable=True)
    time = db.Column(db.DateTime, nullable=True)
    track_id = db.Column(db.Integer, db.ForeignKey('track.id'), nullable=False)

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def parse_gpx(file_path):
    """Parses a GPX file and extracts coordinates."""
    with open(file_path, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)

        coordinates = []
        start_time = None
        end_time = None

        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    coordinates.append((point.latitude, point.longitude, point.speed, point.time))
                    if start_time is None or point.time < start_time:
                        start_time = point.time
                    if end_time is None or point.time > end_time:
                        end_time = point.time

        return coordinates, start_time, end_time

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on the Earth."""
    R = 6371  # Earth radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

@app.route('/')
def index():
    vehicles = db.session.query(Track.vehicle).distinct().all()
    drivers = db.session.query(Track.driver).distinct().all()
    return render_template('index.html', vehicles=vehicles, drivers=drivers)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))

    if file:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        # Parse GPX and save data to database
        coordinates, start_time, end_time = parse_gpx(file_path)
        vehicle = request.form.get('vehicle')
        driver = request.form.get('driver')
        date = request.form.get('date')

        track = Track(name=file.filename, file_path=file_path, vehicle=vehicle, driver=driver, date=date, start_time=start_time, end_time=end_time)
        db.session.add(track)
        db.session.commit()

        for lat, lon, speed, time in coordinates:
            coord = Coordinate(lat=lat, lon=lon, speed=speed, time=time, track_id=track.id)
            db.session.add(coord)
        db.session.commit()

        return redirect(url_for('index'))

@app.route('/filter', methods=['GET', 'POST'])
def filter_tracks():
    vehicle = request.form.get('vehicle')
    driver = request.form.get('driver')
    date_from = request.form.get('date_from')
    date_to = request.form.get('date_to')

    query = Track.query
    if vehicle:
        query = query.filter_by(vehicle=vehicle)
    if driver:
        query = query.filter_by(driver=driver)
    if date_from:
        query = query.filter(Track.date >= date_from)
    if date_to:
        query = query.filter(Track.date <= date_to)

    tracks = query.all()
    return render_template('filtered_tracks.html', tracks=tracks)

@app.route('/track/<int:track_id>')
def view_track(track_id):
    track = Track.query.get_or_404(track_id)
    coordinates = [{'lat': coord.lat, 'lon': coord.lon, 'speed': coord.speed, 'time': coord.time} for coord in track.coordinates]
    total_distance = 0
    avg_speed = 0

    if len(coordinates) > 1:
        distances = []
        for i in range(1, len(coordinates)):
            lat1, lon1 = coordinates[i-1]['lat'], coordinates[i-1]['lon']
            lat2, lon2 = coordinates[i]['lat'], coordinates[i]['lon']
            distance = haversine(lat1, lon1, lat2, lon2)
            distances.append(distance)
        total_distance = sum(distances)

        valid_speeds = [coord['speed'] for coord in coordinates if coord['speed']]
        if valid_speeds:
            avg_speed = sum(valid_speeds) / len(valid_speeds)

    return render_template('view_track.html', track=track, coordinates=coordinates, total_distance=total_distance, avg_speed=avg_speed)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
