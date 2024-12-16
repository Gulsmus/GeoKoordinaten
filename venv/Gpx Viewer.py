from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import os
import gpxpy
import gpxpy.gpx
import math
from datetime import datetime, date

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gpx_data.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database models
class Track(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(150), nullable=True)
    file_path = db.Column(db.String(200), nullable=False)
    vehicle_id = db.Column(db.Integer, db.ForeignKey('vehicle.id'), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey('driver.id'), nullable=False)
    date = db.Column(db.Date, nullable=True)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)

    coordinates = db.relationship('Coordinate', backref='track', lazy=True)
    driver = db.relationship('Driver', back_populates='track')
    vehicle = db.relationship('Vehicle', back_populates='track')

class Coordinate(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    lat = db.Column(db.Float, nullable=False)
    lon = db.Column(db.Float, nullable=False)
    speed = db.Column(db.Float, nullable=True)
    time = db.Column(db.DateTime, nullable=True)
    track_id = db.Column(db.Integer, db.ForeignKey('track.id'), nullable=False)

class Driver(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)

    track = db.relationship('Track', back_populates='driver')
class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)

    track = db.relationship('Track', back_populates='vehicle')

# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def parse_gpx(file_path):
    """Parses a GPX file and extracts coordinates."""
    with open(file_path, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)

        coordinates = []
        start_time = None
        end_time = None
        trackname = 'Unbekannt'

        print(gpx)
        for waypoint in gpx.waypoints:
            coordinates.append((waypoint.latitude,waypoint.longitude,0.0,waypoint.time))
        for track in gpx.tracks:
            trackname = track.name if not None else trackname
            for segment in track.segments:
                for point in segment.points:
                    coordinates.append((point.latitude, point.longitude, point.speed, point.time))
                    if start_time is None or point.time < start_time:
                        start_time = point.time
                    if end_time is None or point.time > end_time:
                        end_time = point.time

        return coordinates, start_time, end_time, trackname

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
    vehicles = db.session.query(Vehicle.name).distinct().all()
    drivers = db.session.query(Driver.name).distinct().all()
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
        file_check = db.session.query(Track).filter(Track.file_path == file_path).first()
        if file_check:
          return redirect(url_for('index'))
        else:
          file.save(file_path)

          # Parse GPX and save data to database
          coordinates, start_time, end_time, track_name = parse_gpx(file_path)
          splitted_filename = file.filename.split('_')
          driver_name = splitted_filename[0]#request.form.get('vehicle')
          vehicle_name = splitted_filename[1]#request.form.get('driver')

          vehicle = db.session.query(Vehicle).filter(Vehicle.name == vehicle_name).first()
          driver = db.session.query(Driver).filter(Driver.name == driver_name).first()
          if not driver:
            driver = Driver(name=driver_name)
            db.session.add(driver)
            db.session.flush()
          if not vehicle:
            vehicle = Vehicle(name=vehicle_name)
            db.session.add(vehicle)
            db.session.flush()
          #date = request.form.get('date')
          track_date = date(start_time.year,start_time.month,start_time.day) if not start_time is None else None

          track = Track(name=track_name, file_path=file_path, vehicle_id=vehicle.id, driver_id=driver.id, date=track_date, start_time=start_time, end_time=end_time)
          db.session.add(track)
          db.session.commit()

          for lat, lon, speed, time in coordinates:
              coord = Coordinate(lat=lat, lon=lon, speed=speed, time=time, track_id=track.id)
              db.session.add(coord)
          db.session.commit()

          return redirect(url_for('index'))

@app.route('/filter', methods=['GET', 'POST'])
def filter_tracks():
    vehicle_name = request.form.get('vehicle')
    driver_name = request.form.get('driver')
    date_from = request.form.get('date_from')
    date_to = request.form.get('date_to')

    query = Track.query
    if vehicle_name:
        query = query.join(Vehicle).filter(Vehicle.name==vehicle_name)
    if driver_name:
        query = query.join(Driver).filter(Driver.name ==driver_name)
    if date_from:
        query = query.filter(Track.date >= date_from)
    if date_to:
        query = query.filter(Track.date <= date_to)

    tracks = query.order_by(Track.date.asc()).all()
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
        total_distance = round(sum(distances),2)

        valid_speeds = [coord['speed'] for coord in coordinates if coord['speed']]
        if valid_speeds:
            avg_speed = sum(valid_speeds) / len(valid_speeds)
            avg_speed = round(avg_speed,2)

    return render_template('view_track.html', track=track, coordinates=coordinates, total_distance=total_distance, avg_speed=avg_speed)

if __name__ == '__main__':
    with app.app_context():
        db.drop_all()
        db.create_all()
    app.run(debug=True)
