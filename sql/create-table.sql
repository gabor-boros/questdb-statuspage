-- Create signals table
CREATE TABLE
    signals(url STRING, http_status INT, received TIMESTAMP, available BOOLEAN)
    timestamp(received);