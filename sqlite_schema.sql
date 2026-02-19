-- SQLite schema for Houser seeds (simplified)

PRAGMA foreign_keys = ON;

-- Countries
CREATE TABLE IF NOT EXISTS countries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  code TEXT,
  created_at TEXT
);

-- Cities
CREATE TABLE IF NOT EXISTS cities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  country_id INTEGER,
  created_at TEXT,
  FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE SET NULL
);

-- Areas
CREATE TABLE IF NOT EXISTS areas (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  city_id INTEGER,
  created_at TEXT,
  FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE SET NULL
);

-- Categories
CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  status TEXT
);

-- AI Prompts
CREATE TABLE IF NOT EXISTS ai_prompts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT UNIQUE,
  name TEXT NOT NULL,
  prompt_text TEXT NOT NULL,
  description TEXT,
  status TEXT,
  created_at TEXT,
  updated_at TEXT
);

-- Properties
CREATE TABLE IF NOT EXISTS properties (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT,
  description TEXT,
  location TEXT,
  price REAL DEFAULT 0,
  bedrooms TEXT,
  bathrooms TEXT,
  amenities TEXT,
  nearby TEXT,
  source TEXT,
  thumbnail TEXT,
  property_type TEXT,
  status TEXT,
  built_status TEXT,
  country_id INTEGER,
  city_id INTEGER,
  area_id INTEGER,
  category_id INTEGER,
  created_at TEXT,
  updated_at TEXT,
  source_url TEXT,
  search_vector TEXT,
  FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE SET NULL,
  FOREIGN KEY (city_id) REFERENCES cities(id) ON DELETE SET NULL,
  FOREIGN KEY (area_id) REFERENCES areas(id) ON DELETE SET NULL,
  FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_properties_status ON properties(status);
CREATE INDEX IF NOT EXISTS idx_properties_type ON properties(property_type);
CREATE INDEX IF NOT EXISTS idx_properties_price ON properties(price);
CREATE INDEX IF NOT EXISTS idx_properties_city_area ON properties(city_id, area_id);
