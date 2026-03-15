USE exam_seating;

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
