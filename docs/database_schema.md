# Database Schema Design for Wiki System

## Overview
This document outlines the database schema design for the wiki system, focusing on pages, versions, and metadata. The schema is designed to be scalable, support core wiki functionalities, and integrate well with SQLAlchemy ORM.

## Entities

### 1. Page
Represents a wiki page with its metadata and content.

**Fields:**
- `id` (INTEGER, PRIMARY KEY)
- `title` (VARCHAR(255), NOT NULL)
- `slug` (VARCHAR(255), UNIQUE, NOT NULL)
- `created_at` (DATETIME, NOT NULL)
- `updated_at` (DATETIME, NOT NULL)
- `created_by` (INTEGER, FOREIGN KEY to users.id)
- `updated_by` (INTEGER, FOREIGN KEY to users.id)
- `is_deleted` (BOOLEAN, DEFAULT FALSE)
- `tags` (JSON, OPTIONAL)
- `categories` (JSON, OPTIONAL)

### 2. PageVersion
Tracks all versions of a page.

**Fields:**
- `id` (INTEGER, PRIMARY KEY)
- `page_id` (INTEGER, FOREIGN KEY to pages.id)
- `version_number` (INTEGER, NOT NULL)
- `content` (TEXT, NOT NULL)
- `summary` (VARCHAR(500), OPTIONAL)
- `created_at` (DATETIME, NOT NULL)
- `created_by` (INTEGER, FOREIGN KEY to users.id)
- `is_current` (BOOLEAN, DEFAULT FALSE)
- `is_deleted` (BOOLEAN, DEFAULT FALSE)

**Constraints:**
- Unique constraint on (page_id, version_number)
- Check constraint to ensure only one current version per page

### 3. Metadata
Stores metadata associated with pages.

**Fields:**
- `id` (INTEGER, PRIMARY KEY)
- `page_id` (INTEGER, FOREIGN KEY to pages.id)
- `key` (VARCHAR(255), NOT NULL)
- `value` (TEXT, NOT NULL)
- `created_at` (DATETIME, NOT NULL)
- `updated_at` (DATETIME, NOT NULL)
- `created_by` (INTEGER, FOREIGN KEY to users.id)
- `updated_by` (INTEGER, FOREIGN KEY to users.id)

**Constraints:**
- Unique constraint on (page_id, key)

## Relationships

- One-to-Many: Page → PageVersions (One page can have multiple versions)
- One-to-Many: Page → Metadata (One page can have multiple metadata entries)
- Many-to-One: PageVersion → Page (Each version belongs to one page)
- Many-to-One: Metadata → Page (Each metadata entry belongs to one page)

## Design Considerations

1. **Scalability:**
   - Using indexed fields for frequently queried columns
   - Storing metadata in JSON format for flexibility
   - Separate version table to allow historical tracking without bloating main page table

2. **SQLAlchemy ORM Integration:**
   - All entities designed with SQLAlchemy declarative syntax
   - Relationships defined using SQLAlchemy's relationship() function
   - Proper foreign key definitions for constraint enforcement

3. **Core Wiki Functionality Support:**
   - Versioning support for content history
   - Metadata storage for tagging and categorization
   - Page creation, editing, and deletion capabilities
   - Efficient querying for latest versions of pages

4. **Best Practices:**
   - Standard naming conventions
   - Appropriate data types
   - Constraints for data integrity
   - Consideration of future extensions

## Future Considerations

- Consider partitioning for very large datasets
- Implement soft-delete patterns where needed
- Add audit logging for changes
- Consider denormalization for read-heavy operations