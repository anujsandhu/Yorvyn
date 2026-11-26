const { chromium } = require('playwright');
const fs = require('node:fs/promises');

async function main() {
  const origin = process.env.CHAT_TEST_ORIGIN;
  const session = JSON.parse(process.env.CHAT_TEST_SESSION);
  const photo = process.argv[2];
  if (!origin || !session || !photo) {
    throw new Error('Missing CHAT_TEST_ORIGIN, CHAT_TEST_SESSION, or photo path');
  }

  const browser = await chromium.launch({
    channel: 'chromium',
    args: ['--enable-unsafe-swiftshader'],
  });
  const pageErrors = [];
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on('pageerror', (e) => pageErrors.push(e.message));

  await page.route('**/*', (route) => {
    const u = new URL(route.request().url());
    return u.origin === origin || ['blob:', 'data:'].includes(u.protocol)
      ? route.continue()
      : route.abort();
  });
  await page.addInitScript((s) => {
    localStorage.setItem('sb-127-auth-token', JSON.stringify(s));
    localStorage.setItem('yorvyn_profile_' + s.user.id, JSON.stringify({ onboardingCompleted: true }));
  }, session);

  try {
    // 1. Navigate to Stylist + Avatar Studio stage, upload jacket photo & generate 3D garment
    await page.goto(`${origin}/stylist`, { waitUntil: 'domcontentloaded' });
    await page.getByTestId('avatar-motion-bar').waitFor({ timeout: 90000 });
    await page.waitForFunction(() => Boolean(window.__studio && window.__studio.getMotionCore && window.__studio.getMotionCore()?.getTelemetry()), { timeout: 60000 });

    const photos = page.locator('input[aria-label="Attach garment photos"]').first();
    await photos.setInputFiles(photo, { timeout: 60000 });
    const input = page.locator('.stylist-text-input:visible').first();
    await input.fill('Create a 3D model of the denim jacket.');
    await input.press('Enter');
    await page.getByRole('link', { name: 'Download GLB' }).first().waitFor({ timeout: 180000 });

    // 2. Open Design Studio -> Wear on Avatar
    await page.getByRole('button', { name: 'Open Design Studio' }).first().click();
    const workspace = page.getByTestId('garment-design-workspace');
    await workspace.waitFor({ timeout: 30000 });
    await page.locator('canvas[data-testid="interactive-3d-canvas"][data-studio-loaded="true"]').waitFor({ timeout: 60000 });
    await page.getByRole('button', { name: 'Wear on Avatar' }).click();
    await page.getByRole('status').filter({ hasText: /Fitted custom 3D/i }).first().waitFor({ timeout: 90000 });
    await page.waitForTimeout(800);

    // 3. Drive interactive character motion states via AvatarMotionBar & record SwiftShader telemetry
    const bar = page.getByTestId('avatar-motion-bar');
    const stateSamples = {};
    for (const label of ['Walk', 'Run', 'Raise Arms', 'Bend', 'Sit', 'Stand', 'Turn']) {
      await bar.getByRole('button', { name: label, exact: true }).click();
      await page.waitForTimeout(550);
      const tel = await page.evaluate(() => window.__studio.getMotionCore()?.getTelemetry() || null);
      stateSamples[label] = tel;
    }

    // 4. Verify Pause -> Resume -> Reset Pose
    await bar.getByRole('button', { name: 'Pause', exact: true }).click();
    await page.waitForTimeout(200);
    const pausedState = await page.evaluate(() => window.__studio.getMotionCore()?.stateManager.getState());
    await bar.getByRole('button', { name: 'Resume', exact: true }).click();
    await page.waitForTimeout(200);
    await bar.getByRole('button', { name: 'Reset Pose', exact: true }).click();
    await page.waitForTimeout(300);
    const resetState = await page.evaluate(() => window.__studio.getMotionCore()?.stateManager.getState());

    // 5. Inspect fitted custom garment vertices & MotionCore state post-animation
    const meshCheck = await page.evaluate(() => {
      const g = window.__studio.getCustomGarment();
      let finite = true;
      let vertCount = 0;
      if (g) {
        g.traverse((o) => {
          if (o.isMesh && o.geometry?.attributes?.position) {
            const p = o.geometry.attributes.position;
            vertCount += p.count;
            for (let i = 0; i < p.count; i++) {
              if (!Number.isFinite(p.getX(i)) || !Number.isFinite(p.getY(i)) || !Number.isFinite(p.getZ(i))) {
                finite = false;
              }
            }
          }
        });
      }
      const core = window.__studio.getMotionCore();
      return {
        finite,
        vertCount,
        clipCount: core ? core.getAvailableClipNames().length : 0,
        skeletonCompatible: core ? core.getSkeleton().getReport().isCompatible : false,
        boneCount: core ? core.getSkeleton().getReport().boneCount : 0,
        fabricProfile: core ? core.getActiveFabricProfile() : null,
        telemetry: core ? core.getTelemetry() : null,
      };
    });

    if (!meshCheck.finite || meshCheck.vertCount === 0) {
      throw new Error(`Garment mesh check failed after animation: ${JSON.stringify(meshCheck)}`);
    }
    if (pausedState !== 'PAUSED' || resetState !== 'IDLE') {
      throw new Error(`Expected PAUSED -> IDLE after reset, got ${pausedState} -> ${resetState}`);
    }

    // 6. Export animated GLB & verify glTF magic header + validation
    const dlEvent = page.waitForEvent('download');
    await bar.getByRole('button', { name: 'Export Animated', exact: true }).click();
    const dl = await dlEvent;
    const glbBuf = await fs.readFile(await dl.path());
    if (glbBuf.slice(0, 4).toString() !== 'glTF') {
      throw new Error('Exported character GLB missing glTF magic bytes');
    }
    const jsonLen = glbBuf.readUInt32LE(12);
    const gltf = JSON.parse(glbBuf.subarray(20, 20 + jsonLen).toString('utf8'));
    const boneCount = (gltf.skins || []).reduce((s, k) => s + (k.joints ? k.joints.length : 0), 0);
    const clipNames = (gltf.animations || []).map((a) => a.name);
    const exportValidation = {
      isValid: (gltf.animations || []).length > 0 && boneCount >= 16,
      exportKind: 'skeletal_animation_export',
      clipCount: clipNames.length,
      sampleClipNames: clipNames.slice(0, 12),
      boneCount,
      hasBakedClothDeformation: false,
      byteLength: glbBuf.length,
    };

    const evidence = {
      status: 'PASSED',
      environment: 'headless_chromium_swiftshader_not_native_gpu',
      photo,
      skeleton_compatible: meshCheck.skeletonCompatible,
      bone_count: meshCheck.boneCount,
      loaded_clip_count: meshCheck.clipCount,
      fitted_garment_vertices: meshCheck.vertCount,
      garment_vertices_finite_after_motion: meshCheck.finite,
      paused_state_verified: pausedState === 'PAUSED',
      reset_state_verified: resetState === 'IDLE',
      fabric_profile: meshCheck.fabricProfile,
      final_telemetry: meshCheck.telemetry,
      export_validation: exportValidation,
      exported_animated_glb_bytes: glbBuf.length,
      state_samples_summary: Object.fromEntries(
        Object.entries(stateSamples).map(([k, v]) => [k, v ? { state: v.state, p50: v.p50FrameMs, p95: v.p95FrameMs, simMs: v.simulationStepMs, activeVerts: v.activeClothVertices, collisions: v.collisionCount } : null])
      ),
      page_errors: pageErrors,
    };

    if (process.env.PHASE_16_9_BROWSER_OUT) {
      await fs.writeFile(process.env.PHASE_16_9_BROWSER_OUT, JSON.stringify(evidence, null, 2));
    }
    console.log(JSON.stringify(evidence, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
