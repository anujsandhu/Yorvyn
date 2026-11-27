"""
YORVYN — Phase 5: Universal Avatar-Aware Garment Fitting, Cloth Physics & Dynamic Deformation Engine
"""

from .avatar_body_measurement_engine import (
    AvatarBodyMeasurementEngine,
    avatar_body_measurement_engine
)
from .garment_ease_engine import (
    GarmentEaseEngine,
    garment_ease_engine
)
from .garment_collision_engine import (
    GarmentCollisionEngine,
    garment_collision_engine
)
from .garment_physics_engine import (
    GarmentPhysicsEngine,
    garment_physics_engine,
    FABRIC_PRESETS
)
from .animation_deformation_validator import (
    AnimationDeformationValidator,
    animation_deformation_validator
)
from .garment_wrinkle_engine import (
    GarmentWrinkleEngine,
    garment_wrinkle_engine
)
from .universal_garment_fitting_engine import (
    UniversalGarmentFittingEngine,
    universal_garment_fitting_engine
)

__all__ = [
    "AvatarBodyMeasurementEngine",
    "avatar_body_measurement_engine",
    "GarmentEaseEngine",
    "garment_ease_engine",
    "GarmentCollisionEngine",
    "garment_collision_engine",
    "GarmentPhysicsEngine",
    "garment_physics_engine",
    "FABRIC_PRESETS",
    "GarmentWrinkleEngine",
    "garment_wrinkle_engine",
    "AnimationDeformationValidator",
    "animation_deformation_validator",
    "UniversalGarmentFittingEngine",
    "universal_garment_fitting_engine",
]

