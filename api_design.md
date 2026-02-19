# API Design for Page CRUD Operations

## Overview
This document defines the REST API endpoints for creating, reading, updating, and deleting pages in the system. Pages can be either static content pages (like 'about', 'contact') or dynamic content pages (like blog posts or dashboard sections).

## Endpoints

### List All Pages
- **GET** `/pages`
- **Description**: Retrieve a list of all pages
- **Query Parameters**:
  - `limit` (optional): Number of results to return (default: 20)
  - `offset` (optional): Number of results to skip (for pagination)
- **Response**:
  ```json
  {
    "pages": [
      {
        "id": "string",
        "title": "string",
        "slug": "string",
        "content": "string",
        "created_at": "datetime",
        "updated_at": "datetime",
        "is_published": "boolean"
      }
    ],
    "total": "integer"
  }
  ```

### Create a New Page
- **POST** `/pages`
- **Description**: Create a new page
- **Request Body**:
  ```json
  {
    "title": "string",
    "slug": "string",
    "content": "string",
    "is_published": "boolean"
  }
  ```
- **Response**: 
  - 201 Created with the created page object

### Get a Specific Page
- **GET** `/pages/{id}`
- **Description**: Retrieve a specific page by ID
- **Response**:
  ```json
  {
    "id": "string",
    "title": "string",
    "slug": "string",
    "content": "string",
    "created_at": "datetime",
    "updated_at": "datetime",
    "is_published": "boolean"
  }
  ```

### Update a Page
- **PUT** `/pages/{id}`
- **Description**: Update a specific page
- **Request Body**:
  ```json
  {
    "title": "string",
    "slug": "string",
    "content": "string",
    "is_published": "boolean"
  }
  ```
- **Response**: 
  - 200 OK with the updated page object

### Delete a Page
- **DELETE** `/pages/{id}`
- **Description**: Delete a specific page
- **Response**: 
  - 204 No Content

## Error Responses
All endpoints may return standard HTTP error codes:
- 400 Bad Request: Invalid request body or parameters
- 404 Not Found: Page with the specified ID does not exist
- 500 Internal Server Error: Server-side error

## Data Model
- `id` (string): Unique identifier for the page
- `title` (string): Title of the page (required)
- `slug` (string): URL-friendly version of the title (required)
- `content` (string): Page content (required)
- `is_published` (boolean): Whether the page is published (default: false)
- `created_at` (datetime): Timestamp when page was created
- `updated_at` (datetime): Timestamp when page was last updated