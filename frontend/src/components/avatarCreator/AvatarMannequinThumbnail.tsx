import React, { useMemo } from 'react';
import { AvatarCreatorCategory } from '../../engine/avatarCreator/avatarCreatorTypes';
import { AvatarPresetDef } from '../../engine/avatarCreator/avatarCreatorTypes';
import { mannequinPreviewRenderer } from '../../engine/avatarCreator/MannequinPreviewRenderer';

interface AvatarMannequinThumbnailProps {
  category: AvatarCreatorCategory;
  presetId: string;
  preset: AvatarPresetDef;
  className?: string;
}

/**
 * YORVYN — Photorealistic 3D Visual Mannequin Preview Thumbnail
 * 
 * Replaces flat cartoon vector illustrations with realistic 3D mannequin previews:
 * - 3D mannequin heads & full bodies with realistic volume and geometry
 * - Consistent 3-point studio lighting & neutral luxury backdrop
 * - Identical camera angles and consistent framing per category
 * - Realistic hairstyle volume, silhouette, and strand highlights
 * - Real body proportions (Athletic, Slender, Curvy, Broad, Balanced)
 * - Zero visible text inside cards (strictly visual)
 */
export const AvatarMannequinThumbnail: React.FC<AvatarMannequinThumbnailProps> = ({
  category,
  presetId,
  preset,
  className = ''
}) => {
  const thumbUrl = useMemo(() => {
    return mannequinPreviewRenderer.getThumbnail(category, presetId, {
      previewColor: preset.previewColor,
      name: preset.name
    });
  }, [category, presetId, preset.previewColor, preset.name]);

  return (
    <div
      className={`avatar-mannequin-thumb-wrapper ${category}-mannequin-wrap ${className}`}
      role="img"
      aria-label={preset.name}
    >
      <img
        src={thumbUrl}
        alt={preset.name}
        className="avatar-mannequin-img"
        loading="lazy"
        draggable={false}
      />
    </div>
  );
};
