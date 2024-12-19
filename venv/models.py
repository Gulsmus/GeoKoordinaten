# -*- coding: utf-8 -*-
from sqlalchemy                 import create_engine, Column, Table, ForeignKey, Index, UniqueConstraint, MetaData, SmallInteger, Integer, String, Date, DateTime, Float, Boolean, Text, Numeric, DateTime
from sqlalchemy.orm             import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.pool            import NullPool

Base = declarative_base()

def db_connect():
  connection_string = "sqlite:///instance/gpx_data.db"
  return create_engine(connection_string, poolclass=NullPool)
  
def create_table(engine):
  Base.metadata.create_all(engine)
  
class Track(Base):
  __tablename__ = "track"
  id = Column(Integer, primary_key=True, autoincrement=True)
  name = Column(String(150), nullable=True)
  file_path = Column(String(200), nullable=False)
  vehicle_id = Column(Integer, ForeignKey('vehicle.id'), nullable=False)
  driver_id = Column(Integer, ForeignKey('driver.id'), nullable=False)
  date = Column(Date, nullable=True)
  total_distance = Column(Float, nullable=False, server_default='0')
  avg_speed = Column(Float, nullable=False, server_default='0')
  start_time = Column(DateTime, nullable=True)
  end_time = Column(DateTime, nullable=True)

  coordinates = relationship('Coordinate', backref='track', lazy=True)
  driver = relationship('Driver', back_populates='track')
  vehicle = relationship('Vehicle', back_populates='track')
  
class Coordinate(Base):
  __tablename__ = 'coordinate'
  id = Column(Integer, primary_key=True, autoincrement=True)
  lat = Column(Float, nullable=False)
  lon = Column(Float, nullable=False)
  ele = Column(Float, nullable=False, server_default='0.0')
  speed = Column(Float, nullable=True)
  time = Column(DateTime, nullable=True)
  track_id = Column(Integer, ForeignKey('track.id'), nullable=False)
    
class Driver(Base):
  __tablename__ = 'driver'
  id = Column(Integer, primary_key=True, autoincrement=True)
  name = Column(String, nullable=False)

  track = relationship('Track', back_populates='driver')
  
class Vehicle(Base):
  __tablename__ = 'vehicle'
  id = Column(Integer, primary_key=True, autoincrement=True)
  name = Column(String, nullable=False)

  track = relationship('Track', back_populates='vehicle')
