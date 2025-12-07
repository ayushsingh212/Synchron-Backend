from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, Form, Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from copy import deepcopy
import json
import logging
from datetime import datetime
import os
from dotenv import load_dotenv
import tempfile
from pathlib import Path
from nlp_processor import TimetableNLPProcessor
from db_utils import get_config_by_params

# =============================================================================
# CONFIGURATION & SETUP
# =============================================================================

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic here
    if USE_CEREBRAS:
        print("Using Cerebras Inference")
    elif llm_extractor:
        print("Using Gemini API")
    else:
        print("WARNING: No LLM extraction available!")
        print("   Please set CEREBRAS_API_KEY or GEMINI_API_KEY")
        print("   in your environment variables.")

    if USE_CEREBRAS:
        print("\nCerebras Ultra-Fast Extraction Ready!")
    elif llm_extractor:
        print("\nLLM extraction is ready")
    else:
        print("\nLLM extraction disabled")

    print("\nAPI Documentation available at:")
    print("Swagger UI: http://localhost:8000/docs")
    print("ReDoc: http://localhost:8000/redoc")
    print("="*60 + "\n")
    yield

# Initialize FastAPI app
app = FastAPI(
    title="Smart Timetable Generator API",
    description="Ultra-fast timetable generation with Cerebras/Gemini LLM",
    version="3.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# App configuration
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'.pdf', '.xlsx', '.xls', '.xlsm', '.json'}

# =============================================================================
# PYDANTIC MODELS
# =============================================================================

class GenerateRequest(BaseModel):
    """Request model for timetable generation"""
    config: Optional[Dict[str, Any]] = None

class DynamicUpdateRequest(BaseModel):
    """Request model for dynamic updates with events"""
    events: List[Dict[str, Any]] = []
    config: Optional[Dict[str, Any]] = None
    # New fields for Database Fetching
    course: Optional[str] = None
    year: Optional[str] = None
    semester: Optional[str] = None
    organisation_id: Optional[str] = None

class StatusResponse(BaseModel):
    """Response model for status endpoint"""
    status: str
    timestamp: Optional[str] = None
    error: Optional[str] = None
    has_parsed_config: bool
    has_results: bool
    llm_backend: str

class NLPRequest(BaseModel):
    """Model for the raw JSON POST body to the NLP endpoint."""
    text: str = Field(..., description="The natural language text describing constraints or events.")
    course: str = Field(..., description="Course Name (e.g., b.tech)")
    year: str = Field(..., description="Year (e.g., 2nd)")
    semester: str = Field(..., description="Semester (e.g., 3rd)")
    organisation_id: Optional[str] = Field(None, description="The MongoDB ObjectId of the Organisation")

# =============================================================================
# ULTRA-FAST LLM EXTRACTOR SETUP WITH CEREBRAS + GEMINI FALLBACK
# =============================================================================

# Initialize LLM-based timetable extractor with priority order
llm_extractor = None
USE_CEREBRAS = False

# Try Cerebras first (ultra-fast)
try:
    from timetable_extractor_gemini import TimetableExtractor
    CEREBRAS_API_KEY = os.getenv('CEREBRAS_API_KEY')
    
    if CEREBRAS_API_KEY:
        llm_extractor = TimetableExtractor(CEREBRAS_API_KEY)
        USE_CEREBRAS = True
        logger.info("Using Cerebras for ultra-fast extraction")
    else:
        logger.warning("Cerebras API key not available")
except ImportError:
    logger.info("Cerebras extractor not available, trying Gemini")
except Exception as e:
    logger.warning(f"Cerebras initialization failed: {e}")

# Fallback to Gemini if Cerebras not available
if not llm_extractor:
    try:
        from timetable_extractor_gemini import TimetableExtractor
        GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
        
        if GEMINI_API_KEY:
            llm_extractor = TimetableExtractor(GEMINI_API_KEY)
            logger.info("Gemini LLM extractor initialized successfully")
            print("Using Gemini LLM extraction as fallback")
        else:
            logger.warning("Gemini API key not available - LLM extraction disabled")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini extractor: {e}")
        llm_extractor = None

# Import timetable modules
try:
    from timetable_generator import GeneticAlgorithm, TimetableData, TimetableExporter
except ImportError as e:
    logger.error(f"Failed to import timetable modules: {e}")

# =============================================================================
# GLOBAL STATE MANAGEMENT
# =============================================================================

# Store the latest timetable generation results
timetable_results = {
    "status": "not_started",
    "timestamp": None,
    "data": None,
    "parsed_config": None
}

# Store dynamic update results
latest_dynamic_update = {
    "status": "not_started",
    "timestamp": None,
    "data": None,
    "events": None
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def allowed_file(filename: str) -> bool:
    """Check if uploaded file has allowed extension"""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS

async def generate_timetables_async(config_data: Optional[Dict] = None):
    """
    Generate timetables in background
    Args:
        config_data (dict): Configuration to use, or None to use default
    """
    global timetable_results
    try:
        # Update status to in progress
        timetable_results["status"] = "in_progress"
        timetable_results["timestamp"] = datetime.now().isoformat()
        
        # Use provided config or load from file
        if config_data:
            config = config_data
            logger.info("Using provided configuration for generation")
        else:
            try:
                with open('corrected_timetable_config.json', 'r') as f:
                    config = json.load(f)
                logger.info("Using default configuration file")
            except FileNotFoundError:
                timetable_results["status"] = "failed"
                timetable_results["error"] = "Default config file not found!"
                return
        
        # Initialize timetable data and genetic algorithm
        logger.info("Initializing timetable generation...")
        data = TimetableData(config_dict=config)
        ga = GeneticAlgorithm(data)
        
        # Generate population and evolve
        ga.initialize_population()
        ga.evolve()
        
        # Get the best solution
        best_solution = ga.get_best_solution()
        if not best_solution:
            timetable_results["status"] = "failed"
            timetable_results["error"] = "No valid solution found!"
            logger.error("Failed to find valid timetable solution")
            return
        
        # Export results in all formats
        logger.info("Exporting timetable results...")
        exporter = TimetableExporter(best_solution, data)
        
        # Store all generated data
        timetable_results["data"] = {
            "sections": exporter.get_section_wise_data(),
            "faculty": exporter.get_faculty_wise_data(),
            "detailed": exporter.get_detailed_data(),
            "statistics": exporter.get_statistics()
        }
        
        # Mark as completed
        timetable_results["status"] = "completed"
        timetable_results["timestamp"] = datetime.now().isoformat()
        logger.info("Timetable generation completed successfully")
        
    except Exception as e:
        timetable_results["status"] = "failed"
        timetable_results["error"] = str(e)
        logger.error(f"Timetable generation failed: {str(e)}")

def apply_events_to_config(config: Dict, events: List[Dict]) -> Dict:
    """
    Apply event constraints:
    1. Faculty Absence -> Add to faculty['unavailable_periods']
    2. Room Unavailable -> Add to rooms['unavailable_periods']
    3. Section Unavailable -> (NEW) Add to sections['unavailable_periods'] (requires GA support) or strictly block slots
    4. Force Assignment -> (NEW) Add to 'fixed_assignments' in special_requirements
    """
    modified_config = deepcopy(config)
    
    # Ensure helper structures exist
    if 'special_requirements' not in modified_config:
        modified_config['special_requirements'] = {}
    if 'fixed_assignments' not in modified_config['special_requirements']:
        modified_config['special_requirements']['fixed_assignments'] = []

    day_mapping = {day: idx for idx, day in enumerate(modified_config.get('time_slots', {}).get('working_days', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']))}
    
    for event in events:
        event_type = event.get('type')
        start_day = event.get('start_day')
        end_day = event.get('end_day')
        timeslots = event.get('timeslots') # None means all day
        
        # Calculate day range indices
        if start_day and end_day:
            start_idx = day_mapping.get(start_day, 0)
            end_idx = day_mapping.get(end_day, len(day_mapping) - 1)
            day_range = list(range(start_idx, end_idx + 1))
        else:
            day_range = []

        # 1. Faculty Absence
        if event_type in ['faculty_absence', 'faculty_partial_absence']:
            fid = event.get('faculty_id')
            # ... (existing faculty logic logic, see below for robust implementation) ...
            for faculty in modified_config.get('faculty', []):
                if faculty.get('faculty_id') == fid:
                    if 'unavailable_periods' not in faculty: faculty['unavailable_periods'] = []
                    
                    # Logic: If timeslots is None, block ALL periods for days in range
                    periods_to_block = timeslots if timeslots else [p['id'] for p in modified_config['time_slots']['periods']]
                    
                    for d in day_range:
                        for p in periods_to_block:
                            faculty['unavailable_periods'].append({'day': d, 'period': p})

        # 2. Resource/Room Unavailable
        elif event_type in ['resource_unavailable', 'room_maintenance']:
            rid = event.get('room_id')
            for room in modified_config.get('rooms', []):
                if room.get('room_id') == rid:
                    if 'unavailable_periods' not in room: room['unavailable_periods'] = []
                    periods_to_block = timeslots if timeslots else [p['id'] for p in modified_config['time_slots']['periods']]
                    for d in day_range:
                        for p in periods_to_block:
                            room['unavailable_periods'].append({'day': d, 'period': p})

        # 3. Section Unavailable (NEW)
        elif event_type == 'section_unavailable':
            sid = event.get('section_id')
            # We need to find the section and mark unavailable periods.
            # NOTE: The GeneticAlgorithm/Data needs to respect section['unavailable_periods'].
            # If your GA doesn't support it yet, we can hack it by adding a dummy hard constraint 
            # or ensuring the 'is_conflict_free' checks section availability.
            
            # Let's add it to the section dict assuming GA updates:
            found = False
            # Check department sections
            for dept in modified_config.get('departments', []):
                for section in dept.get('sections', []):
                    if section.get('section_id') == sid:
                        if 'unavailable_periods' not in section: section['unavailable_periods'] = []
                        periods_to_block = timeslots if timeslots else [p['id'] for p in modified_config['time_slots']['periods']]
                        for d in day_range:
                            for p in periods_to_block:
                                section['unavailable_periods'].append({'day': d, 'period': p})
                        found = True
            
            # Check loose sections
            if not found:
                for section in modified_config.get('sections', []):
                    if section.get('section_id') == sid:
                        if 'unavailable_periods' not in section: section['unavailable_periods'] = []
                        periods_to_block = timeslots if timeslots else [p['id'] for p in modified_config['time_slots']['periods']]
                        for d in day_range:
                            for p in periods_to_block:
                                section['unavailable_periods'].append({'day': d, 'period': p})

        # 4. Force Assignment (NEW)
        elif event_type == 'force_assignment':
            # "Dr. Smith, Subject X, Section Y, Mon, P1, [Room Z]"
            assignment = {
                "faculty_id": event.get('faculty_id'),
                "subject_id": event.get('subject_id'),
                "section_id": event.get('section_id'),
                "day": day_mapping.get(event.get('day')),
                "period": event.get('timeslot'),
                "room_id": event.get('room_id') # Optional
            }
            # Add to special_requirements.fixed_assignments
            modified_config['special_requirements']['fixed_assignments'].append(assignment)

    return modified_config

# =============================================================================
# MAIN ROUTES
# =============================================================================

@app.get("/")
async def home():
    """Basic health check endpoint"""
    return {
        'message': 'Smart Timetable Generator API with Ultra-Fast Cerebras',
        'status': 'running',
        'version': '3.0',
        'llm_backend': 'Cerebras' if USE_CEREBRAS else 'Gemini'
    }

# =============================================================================
# TIMETABLE PARSING ENDPOINTS
# =============================================================================

@app.post("/api/parse-timetable")
async def parse_timetable(
    file: UploadFile = File(...),
    college_name: Optional[str] = Form(None),
    session: Optional[str] = Form(None)
):
    """
    Parse uploaded PDF/Excel timetable file using ultra-fast LLM
    
    - **file**: PDF, XLSX, XLS, or XLSM file
    - **college_name**: Optional college name
    - **session**: Optional session info
    """
    if not llm_extractor:
        raise HTTPException(
            status_code=503,
            detail='LLM extractor is not available. Please check your API key setup.'
        )
    
    try:
        # Validate file
        if not allowed_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail='Invalid file format. Allowed: PDF, XLSX, XLS, XLSM, JSON'
            )
        
        # Read file content
        file_content = await file.read()
        
        # Check file size
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail='File too large. Maximum size is 50MB.'
            )
        
        filename = file.filename
        extraction_method = "Cerebras (ultra-fast)" if USE_CEREBRAS else "Gemini"
        logger.info(f"Starting {extraction_method} parsing for file: {filename}")
        
        # Extract timetable data using ultra-fast LLM
        start_time = datetime.now()
        result = llm_extractor.extract_timetable_data(
            file_content=file_content,
            filename=filename,
            college_name=college_name,
            session=session
        )
        end_time = datetime.now()
        extraction_time = (end_time - start_time).total_seconds()
        
        # Store parsed config for later use
        timetable_results["parsed_config"] = result
        
        success_message = f"Timetable parsed successfully using {extraction_method}"
        if USE_CEREBRAS:
            success_message += f" in {extraction_time:.2f}s (ultra-fast!)"
        
        logger.info("Timetable parsing completed successfully")
        
        return {
            'success': True,
            'message': success_message,
            'data': result,
            'extraction_info': {
                **result.get('extraction_info', {}),
                'llm_backend': 'Cerebras' if USE_CEREBRAS else 'Gemini',
                'extraction_time_seconds': extraction_time
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Timetable parsing failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f'Failed to parse timetable: {str(e)}'
        )


@app.post("/api/nlp/parse", status_code=200)
async def parse_natural_language(
    request: NLPRequest = Body(...) # Accepts the raw JSON body
):
    """
    Takes natural language text along with context parameters (course, year, semester)
    and returns structured JSON for events or constraints, validated by Pydantic.
    """
    logger.info(f"Received NLP request for {request.course}/{request.year}/{request.semester}")
    
    # 1. Load context from MongoDB using request parameters
    config = get_config_by_params(
        course=request.course,
        year=request.year,
        semester=request.semester,
        organisation_id=request.organisation_id
    )
    
    if not config:
        raise HTTPException(
            status_code=404, 
            detail=f"Configuration not found in DB for: {request.course}/{request.year}/{request.semester}. Cannot parse entities."
        )

    # 2. Initialize Processor (LLM API Key check is inside the Processor's __init__)
    try:
        processor = TimetableNLPProcessor(config)
    except EnvironmentError as e:
        raise HTTPException(status_code=503, detail=f"LLM Processor Error: {e}")

    # 3. Parse and Validate
    result = processor.parse_request(request.text)

    if "error" in result:
        # Pydantic validation failure or LLM failure
        raise HTTPException(status_code=422, detail=result["details"])
    
    # -------------------------------------------------------------------------
    # 4. FIX: Ensure 'config' is JSON-serializable before returning.
    # The default=str handles non-standard types (like ObjectId, datetime) 
    # by converting them to strings.
    try:
        json_safe_config = json.loads(json.dumps(config, default=str))
    except Exception as e:
        logger.error(f"Failed to serialize config for response: {e}")
        raise HTTPException(status_code=500, detail="Failed to serialize configuration from database.")
    # -------------------------------------------------------------------------

    # 5. Return structured data
    return {
        "status": "success",
        "interpreted_data": result,
        "context_source": "database_context",
        "config": json_safe_config, # <-- Return the JSON-safe version
        "config_loaded": f"{request.organisation_id}/{request.course}/{request.year}/{request.semester}"
    }

# =============================================================================
# TIMETABLE GENERATION ENDPOINTS
# =============================================================================

@app.post("/api/generate")
async def generate_timetable(
    request: Optional[Dict[str, Any]] = Body(None)
):
    """
    Generate timetable using configuration and return results directly
    
    Options:
    1. Use JSON configuration from request body
    2. Use default configuration file
    
    Returns the generated timetable data directly without caching
    """
    try:
        config_data = None
        
        # Try to get configuration from request
        if request:
            config_data = request
            logger.info("Using configuration from request body")
        else:
            raise HTTPException(
                status_code=400,
                detail="Config file not found! Please provide configuration in request body."
            )
        
        # Generate timetables synchronously
        try:
            # Build TimetableData from provided config dict
            data_obj = TimetableData(config_dict=config_data)

            genetic_algo = GeneticAlgorithm(data_obj)
            genetic_algo.initialize_population()
            genetic_algo.evolve()

            # NEW: get top 3 solutions
            solutions = genetic_algo.get_best_solution()

            if not solutions:
                raise HTTPException(
                    status_code=400,
                    detail="No valid solution found!"
                )

            exported_solutions = []
            for idx, sol in enumerate(solutions, start=1):
                exporter = TimetableExporter(sol, data_obj)
                exported_solutions.append({
                    "rank": idx,
                    "fitness": sol.fitness_score,
                    "constraint_violations": sol.constraint_violations,
                    "sections": exporter.get_section_wise_data(),
                    "faculty": exporter.get_faculty_wise_data(),
                    "detailed": exporter.get_detailed_data(),
                    "statistics": exporter.get_statistics(),
                })

            logger.info("Timetable generation completed successfully")
            
            return {
                "status": "completed",
                "timestamp": datetime.now().isoformat(),
                "solutions": exported_solutions,  # list of 3
            }

        except Exception as e:
            logger.error(f"Timetable generation failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Generation failed: {str(e)}"
            )

    except Exception as e:
        logger.error(f"Failed to generate timetable: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate timetable: {str(e)}"
        )


# =============================================================================
# STATUS & RESULTS ENDPOINTS
# =============================================================================

@app.get("/api/status")
async def get_status():
    """Get current timetable generation status"""
    return {
        "status": timetable_results["status"],
        "timestamp": timetable_results.get("timestamp"),
        "error": timetable_results.get("error"),
        "has_parsed_config": timetable_results.get("parsed_config") is not None,
        "has_results": timetable_results.get("data") is not None,
        "llm_backend": "Cerebras" if USE_CEREBRAS else "Gemini"
    }

@app.get("/api/results")
async def get_all_results():
    """Get all timetable generation results"""
    if timetable_results["status"] != "completed" or not timetable_results["data"]:
        raise HTTPException(status_code=404, detail="No completed timetables available")
    
    return {
        "status": "success",
        "timestamp": timetable_results["timestamp"],
        "data": timetable_results["data"]
    }

# =============================================================================
# SECTION TIMETABLE ENDPOINTS
# =============================================================================

@app.get("/api/timetables/sections")
async def get_all_sections():
    """Get all section timetables"""
    if timetable_results["status"] != "completed" or not timetable_results["data"]:
        raise HTTPException(status_code=404, detail="No timetables generated yet")
    
    return timetable_results["data"]["sections"]

@app.get("/api/timetables/sections/{section_id}")
async def get_single_section(section_id: str):
    """Get specific section timetable"""
    if timetable_results["status"] != "completed" or not timetable_results["data"]:
        raise HTTPException(status_code=404, detail="No timetables generated yet")
    
    section_data = timetable_results["data"]["sections"].get(section_id)
    if not section_data:
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found")
    
    return section_data

# =============================================================================
# FACULTY TIMETABLE ENDPOINTS
# =============================================================================

@app.get("/api/timetables/faculty")
async def get_all_faculty():
    """Get all faculty timetables"""
    if timetable_results["status"] != "completed" or not timetable_results["data"]:
        raise HTTPException(status_code=404, detail="No timetables generated yet")
    
    return timetable_results["data"]["faculty"]

@app.get("/api/timetables/faculty/{faculty_id}")
async def get_single_faculty(faculty_id: str):
    """Get specific faculty timetable"""
    if timetable_results["status"] != "completed" or not timetable_results["data"]:
        raise HTTPException(status_code=404, detail="No timetables generated yet")
    
    faculty_data = timetable_results["data"]["faculty"].get(faculty_id)
    if not faculty_data:
        raise HTTPException(status_code=404, detail=f"Faculty '{faculty_id}' not found")
    
    return faculty_data

# =============================================================================
# DETAILED & STATISTICS ENDPOINTS
# =============================================================================

@app.get("/api/timetables/detailed")
async def get_detailed_timetable():
    """Get detailed timetable data (all entries in list format)"""
    if timetable_results["status"] != "completed" or not timetable_results["data"]:
        raise HTTPException(status_code=404, detail="No timetables generated yet")
    
    return timetable_results["data"]["detailed"]

@app.get("/api/timetables/statistics")
async def get_statistics():
    """Get timetable generation statistics"""
    if timetable_results["status"] != "completed" or not timetable_results["data"]:
        raise HTTPException(status_code=404, detail="No timetables generated yet")
    
    return timetable_results["data"]["statistics"]

# =============================================================================
# CONFIGURATION ENDPOINTS
# =============================================================================

@app.get("/api/config/parsed")
async def get_parsed_config():
    """Get the most recently parsed configuration"""
    if not timetable_results.get("parsed_config"):
        raise HTTPException(status_code=404, detail="No parsed configuration available")
    
    return timetable_results["parsed_config"]

@app.post("/api/config/validate")
async def validate_config(config: Dict[str, Any] = Body(...)):
    """
    Validate a timetable configuration
    
    Expected: JSON configuration in request body
    """
    try:
        # Check required fields
        required_fields = [
            'college_info', 'time_slots', 'departments',
            'subjects', 'faculty', 'rooms'
        ]
        
        missing_fields = [field for field in required_fields if field not in config]
        if missing_fields:
            return {
                'valid': False,
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }
        
        # Try to create TimetableData object to validate
        try:
            data = TimetableData(config_dict=config)
            return {
                'valid': True,
                'message': 'Configuration is valid',
                'stats': {
                    'departments': len(data.departments),
                    'sections': len(data.sections),
                    'subjects': len(data.subjects),
                    'faculty': len(data.faculty),
                    'rooms': len(data.rooms),
                    'periods': len(data.period_ids)
                }
            }
        except Exception as validation_error:
            return {
                'valid': False,
                'error': f'Configuration validation failed: {str(validation_error)}'
            }
    
    except Exception as e:
        logger.error(f"Config validation error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f'Failed to validate configuration: {str(e)}'
        )

# =============================================================================
# DYNAMIC UPDATE ENDPOINTS
# =============================================================================

# =============================================================================
# DYNAMIC UPDATE ENDPOINTS - REGENERATE TIMETABLE WITH EVENTS
# =============================================================================

@app.post("/api/regenerate-with-events")
async def regenerate_with_events(
    request: DynamicUpdateRequest = Body(...)
):
    """
    Regenerate with extended event handling.
    Prioritizes Config from:
    1. Request Body (request.config)
    2. MongoDB (using request.course/year/semester)
    3. In-Memory Cache (timetable_results)
    """
    try:
        logger.info(f"Regenerating with {len(request.events)} events")

        # -----------------------------------------------------------------
        # 1. RESOLVE CONFIGURATION
        # -----------------------------------------------------------------
        base_config = request.config

        # If not in body, try fetching from Database
        if not base_config and request.organisation_id and request.course and request.year and request.semester:
            logger.info(f"Fetching config from DB for {request.organisation_id}/{request.course} / {request.year} / {request.semester}")
            base_config = get_config_by_params(
                course=request.course,
                year=request.year,
                semester=request.semester,
                organisation_id=request.organisation_id
            )
            if not base_config:
                logger.warning("Database params provided but no config found.")

        # If still not found, try the in-memory cache (last parsed file)
        if not base_config:
            logger.info("Checking in-memory cache for configuration...")
            base_config = timetable_results.get("parsed_config")

        # Final validation
        if not base_config:
            raise HTTPException(
                status_code=400, 
                detail="No configuration found! Please provide 'config' in body, or valid 'course'/'year'/'semester' parameters, or parse a file first."
            )

        # -----------------------------------------------------------------
        # 2. APPLY EVENTS
        # -----------------------------------------------------------------
        # Deepcopy to avoid modifying the source config permanently
        modified_config = deepcopy(base_config)

        # Apply Events (Absences, Force Assigns, etc.)
        modified_config = apply_events_to_config(modified_config, request.events)

        # -----------------------------------------------------------------
        # 3. GENERATE TIMETABLE
        # -----------------------------------------------------------------
        data_obj = TimetableData(config_dict=modified_config)
        
        genetic_algo = GeneticAlgorithm(data_obj)
        genetic_algo.initialize_population()
        genetic_algo.evolve()

        solutions = genetic_algo.get_best_solution()
        if not solutions:
            logger.error("No valid solution found with event constraints")
            raise HTTPException(
                status_code=400,
                detail="No valid solution found with event constraints"
            )

        # Export solutions
        exported_solutions = []
        for idx, sol in enumerate(solutions, start=1):
            exporter = TimetableExporter(sol, data_obj)
            exported_solutions.append({
                "rank": idx,
                "fitness": sol.fitness_score,
                "constraint_violations": sol.constraint_violations,
                "sections": exporter.get_section_wise_data(),
                "faculty": exporter.get_faculty_wise_data(),
                "detailed": exporter.get_detailed_data(),
                "statistics": exporter.get_statistics(),
            })

        logger.info("Timetable regeneration with events completed successfully (synchronous)")

        return {
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "events_applied": len(request.events),
            "config_source": "database" if (not request.config and request.course) else "request/cache",
            "solutions": exported_solutions
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regeneration error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate timetable: {str(e)}"
        )

# =============================================================================
# SYSTEM ENDPOINTS
# =============================================================================

@app.get("/api/health")
async def health_check():
    """Comprehensive health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'llm_backend': 'Cerebras' if USE_CEREBRAS else 'Gemini',
        'llm_configured': llm_extractor is not None,
        'cerebras_available': USE_CEREBRAS,
        'gemini_api_available': os.getenv('GEMINI_API_KEY') is not None,
        'generation_status': timetable_results["status"],
        'dynamic_update_status': latest_dynamic_update["status"],
        'features': {
            'ultra_fast_extraction': USE_CEREBRAS,
            'llm_extraction': llm_extractor is not None,
            'genetic_algorithm': True,
            'dynamic_updates': True,
            'multi_format_support': True
        }
    }


# =============================================================================
# RUN THE APPLICATION
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )