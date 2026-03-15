-- Create Database
CREATE DATABASE IF NOT EXISTS exam_seating;
USE exam_seating;

-- Drop existing tables one by one
DROP TABLE IF EXISTS allocated_invigilator;
DROP TABLE IF EXISTS allocations;
DROP TABLE IF EXISTS exam_sessions;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS halls;
DROP TABLE IF EXISTS invigilators;
DROP TABLE IF EXISTS admins;

-- Students Table (with password for login)
CREATE TABLE students (
    id INT AUTO_INCREMENT PRIMARY KEY,
    register_number VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(10) NOT NULL,
    join_year INT NOT NULL,
    current_year INT NOT NULL,
    password VARCHAR(100) DEFAULT 'student123'
);

-- Halls Table
CREATE TABLE halls (
    id INT AUTO_INCREMENT PRIMARY KEY,
    hall_name VARCHAR(50) NOT NULL,
    total_rows INT NOT NULL,
    total_columns INT DEFAULT 9
);

-- Invigilators Table (with staff_id and availability)
CREATE TABLE invigilators (
    id INT AUTO_INCREMENT PRIMARY KEY,
    staff_id VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(50),
    availability ENUM('Available', 'Unavailable') DEFAULT 'Available'
);

-- Exam Sessions Table (no manual invigilator assignment)
CREATE TABLE exam_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    session_type VARCHAR(10) NOT NULL,
    time_slot VARCHAR(50) NOT NULL,
    session_date DATE NOT NULL,
    -- Store multiple selected years as comma-separated values, e.g. '1,2,3'
    years VARCHAR(50) NOT NULL,
    hall_id INT NOT NULL,
    FOREIGN KEY (hall_id) REFERENCES halls(id)
);

-- Allocations Table (student seating)
CREATE TABLE allocations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    session_id INT NOT NULL,
    hall_id INT NOT NULL,
    `row_number` INT NOT NULL,
    `column_name` VARCHAR(5) NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (session_id) REFERENCES exam_sessions(id),
    FOREIGN KEY (hall_id) REFERENCES halls(id),
    UNIQUE KEY unique_seat (session_id, `row_number`, `column_name`)
);

-- Allocated Invigilator Table (automatic assignment)
CREATE TABLE allocated_invigilator (
    id INT AUTO_INCREMENT PRIMARY KEY,
    invigilator_id INT NOT NULL,
    hall_id INT NOT NULL,
    session_id INT NOT NULL,
    assigned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (invigilator_id) REFERENCES invigilators(id),
    FOREIGN KEY (hall_id) REFERENCES halls(id),
    FOREIGN KEY (session_id) REFERENCES exam_sessions(id),
    UNIQUE KEY unique_invigilator_session (session_id, hall_id)
);

-- Invigilator Session Availability Table (session-specific availability)
CREATE TABLE invigilator_session_availability (
    id INT AUTO_INCREMENT PRIMARY KEY,
    invigilator_id INT NOT NULL,
    session_id INT NOT NULL,
    status ENUM('Available', 'Unavailable') DEFAULT 'Available',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (invigilator_id) REFERENCES invigilators(id),
    FOREIGN KEY (session_id) REFERENCES exam_sessions(id),
    UNIQUE KEY unique_invigilator_session (invigilator_id, session_id)
);

-- Admin Table (for login)
CREATE TABLE admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL
);

-- Create the new invigilator_session_availability table
CREATE TABLE invigilator_session_availability (
    id INT AUTO_INCREMENT PRIMARY KEY,
    invigilator_id INT NOT NULL,
    session_id INT NOT NULL,
    status ENUM('Available', 'Unavailable') DEFAULT 'Available',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (invigilator_id) REFERENCES invigilators(id),
    FOREIGN KEY (session_id) REFERENCES exam_sessions(id),
    UNIQUE KEY unique_invigilator_session (invigilator_id, session_id)
);
-- Insert default admin
INSERT INTO admins (username, password) VALUES ('admin', 'admin123');