-- Initialize database for war_site
-- This script runs when the PostgreSQL container starts for the first time

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Set timezone
SET timezone = 'Europe/Moscow';

-- Create indexes for better performance (will be created by Django migrations)
-- This is just a placeholder for any custom database setup