"""Canonical provider record for nationwide directory extraction."""

from copy import deepcopy


DAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


def new_provider():
    """Create a provider record with all fields initialized."""

    return {
        "provider_id": None,
        "name": None,
        "business_name": None,
        "contact_person": None,
        "provider_type": None,
        "organization_type": None,
        "description": None,

        "contact": {
            "phones": [],
            "emails": [],
            "website": None,
            "booking_url": None,
        },

        "location": {
            "street_address": None,
            "address_line_2": None,
            "city": None,
            "county": None,
            "state": None,
            "postal_code": None,
            "country": "US",
            "latitude": None,
            "longitude": None,
            "address_visibility": None,
        },

        "service_areas": {
            "counties": [],
            "cities": [],
            "states": [],
            "raw_text": None,
        },

        "services": {
            "supervised_visitation": None,
            "supervised_exchange": None,
            "virtual_visitation": None,
            "telephone_monitoring": None,
            "transportation": None,
            "pickup_dropoff": None,
            "overnight_visitation": None,
            "court_reports": None,
            "other_services": [],
        },

        "pricing": {
            "currency": "USD",
            "hourly_rate": {
                "min": None,
                "max": None,
            },
            "intake_fee": None,
            "orientation_fee": None,
            "report_fee": None,
            "exchange_fee": None,
            "additional_child_fee": None,
            "transportation_fee": None,
            "cancellation_fee": None,
            "minimum_hours": None,
            "sliding_scale_available": None,
            "financial_assistance_available": None,
            "raw_pricing_text": None,
        },

        "availability": {
            "timezone": None,
            "days": {
                day: {
                    "available": None,
                    "hours": [],
                }
                for day in DAYS
            },
            "weekends_available": None,
            "evenings_available": None,
            "holidays_available": None,
            "overnight_available": None,
            "appointment_required": None,
            "accepting_new_clients": None,
            "availability_last_confirmed": None,
            "raw_hours_text": None,
        },

        "visitation": {
            "onsite_available": None,
            "offsite_available": None,
            "home_visits_available": None,
            "community_visits_available": None,
            "minimum_visit_minutes": None,
            "maximum_visit_minutes": None,
            "virtual_visits_available": None,
            "raw_location_text": None,
            "raw_duration_text": None,
        },

        "languages": [],

        "qualifications": {
            "trustline_registered": None,
            "background_check": None,
            "training_24_hours": None,
            "mandated_reporter_training": None,
            "fl324p_declaration": None,
            "licenses": [],
            "certifications": [],
            "insurance_verified": None,
        },

        "court_listings": [],

        "verification": {
            "status": "unverified",
            "last_verified_at": None,
            "verified_by": None,
            "provider_claimed": False,
            "provider_claimed_at": None,
        },

        "source": {
            "type": None,
            "state": None,
            "county": None,
            "url": None,
            "local_file": None,
            "extraction_engine": None,
            "extracted_at": None,
            "raw_provider_text": None,
        },

        "metadata": {
            "created_at": None,
            "updated_at": None,
            "extraction_confidence": None,
            "review_required": True,
        },
    }


def clone_provider(provider):
    """Return an independent copy of a provider record."""
    return deepcopy(provider)
