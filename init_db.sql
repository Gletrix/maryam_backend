-- Database initialization for Portfolio WebApp
-- Run this on Railway Postgres to create tables
-- Railway DB: Set DATABASE_URL env var with postgres://user:pass@host:port/dbname

-- Posts table: Stores design portfolio posts with optional media
CREATE TABLE IF NOT EXISTS posts (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    media_path VARCHAR(500),           -- File path or null for text-only posts
    media_type VARCHAR(20),            -- 'image', 'video', or null
    thumbnail_path VARCHAR(500),       -- Thumbnail for videos or optimized image
    is_draft BOOLEAN DEFAULT FALSE,
    media_data BYTEA,                  -- For DB storage option (MEDIA_STORAGE=db)
    thumbnail_data BYTEA,              -- Thumbnail binary data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Contact messages table: Stores messages from contact form
CREATE TABLE IF NOT EXISTS contact_messages (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Contact info table: Single row for editable contact information
CREATE TABLE IF NOT EXISTS contact_info (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- Enforce single row
    email VARCHAR(255),
    phone VARCHAR(50),
    social_json JSONB DEFAULT '{}',    -- {instagram: "...", linkedin: "...", etc}
    bio TEXT,                          -- Short bio for About page
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert default contact info row
INSERT INTO contact_info (id, email, phone, social_json, bio)
VALUES (1, 'designer@example.com', '', '{}', 'Graphic designer passionate about visual storytelling.')
ON CONFLICT (id) DO NOTHING;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_is_draft ON posts(is_draft);
CREATE INDEX IF NOT EXISTS idx_contact_messages_created_at ON contact_messages(created_at DESC);
