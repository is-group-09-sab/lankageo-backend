-- SQL to create the case_studies table in Supabase
-- Aligned with Frontend CaseStudy interface

CREATE TABLE IF NOT EXISTS case_studies (
    id TEXT PRIMARY KEY, -- String ID (e.g., 'colombo-port-2024')
    title TEXT NOT NULL,
    category TEXT NOT NULL, -- e.g., 'Infrastructure', 'Environment'
    summary TEXT,
    content TEXT,
    image_url TEXT, -- Thumbnail for listing
    images TEXT[] DEFAULT '{}', -- Array of image URLs for detailed view
    analysis JSONB DEFAULT '{}', -- Detailed analysis data (rainfall, impact, etc.)
    stats JSONB DEFAULT '[]', -- Array of stat objects [{label: "...", value: "..."}]
    date TEXT, -- Matches frontend "2024.Q1" style
    location TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_case_studies_category ON case_studies(category);

-- Enable Row Level Security (RLS) if needed
-- ALTER TABLE case_studies ENABLE ROW LEVEL SECURITY;

-- Policy: Allow public read access
-- CREATE POLICY "Allow public read access" ON case_studies FOR SELECT USING (true);
