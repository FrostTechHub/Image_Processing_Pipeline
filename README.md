# HTX Digital Forensics Internship - Take Home Assessment

## Submission Details
**Name:** Muhammad Fizry Bin Ridzwan

## 1. Project Overview
This project implements a RESTful Image Processing Pipeline API as part of the Digital Forensics Internship – Software Engineering Assessment 

The system is designed to automatically process uploaded images, generate thumbnails, extract metadata, perform AI-based image captioning, and expose the processed results through structured API endpoints.

The API supports JPEG and PNG image uploads and performs the following automated processing steps:
    * Accepts image uploads via POST /api/images
    * Generates two thumbnail sizes (small and medium)
    * Extracts core metadata including dimensions, file format, file size, and timestamp
    * Generates an AI-based image caption using a publicly available model
    * Stores processing results in persistent storage
    * Provides structured JSON responses following the required response format
    * Exposes thumbnail images via dedicated retrieval endpoints
    * Tracks processing statistics including success rate and average processing time

The system follows RESTful API design principles and separates concerns between:
    * Image storage
    * Metadata extraction
    * Thumbnail generation
    * AI analysis
    * API response handling
    * Processing statistics tracking

Error handling is implemented to gracefully manage:
    * Unsupported file formats
    * Corrupted image files
    * Processing failures
    * AI inference errors

Processing logs are recorded using structured logging to support traceability and debugging. This implementation is designed to be modular, extensible, and production-oriented, with optional support for asynchronous processing and job queuing for improved scalability.

## 2. Installation Steps

## 3. API Documentation

## 4. Sample Usage (i.e. How to run the code...)

## 5. Processing Pipeline Explanation
