const RUNTIME_DEFAULTS = {
  languages: ['ru', 'kz', 'en'],
  defaultLanguage: 'ru',
  idleTimeoutSeconds: 15,
  kitchenWarningRatio: 0.7,
  displayReadyVisibilitySeconds: 300,
  serviceModes: {
    enabled: ['dine_in', 'takeaway'],
    default: 'dine_in'
  }
}

function normalizeLanguage(value) {
  return String(value || '').trim().toLowerCase()
}

function normalizeServiceMode(value) {
  return String(value || '').trim().toLowerCase()
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

export function buildEffectiveRuntimeSettings(settingsPayload) {
  const effective = settingsPayload?.effective || {}

  const languages = Array.isArray(effective.languages) && effective.languages.length > 0
    ? effective.languages.map(normalizeLanguage).filter(Boolean)
    : RUNTIME_DEFAULTS.languages

  const defaultLanguageCandidate = normalizeLanguage(effective.default_language)
  const defaultLanguage = languages.includes(defaultLanguageCandidate)
    ? defaultLanguageCandidate
    : RUNTIME_DEFAULTS.defaultLanguage

  const enabledModesRaw = Array.isArray(effective?.service_modes?.enabled)
    ? effective.service_modes.enabled.map(normalizeServiceMode).filter(Boolean)
    : RUNTIME_DEFAULTS.serviceModes.enabled

  const enabledModes = enabledModesRaw.length > 0
    ? enabledModesRaw
    : RUNTIME_DEFAULTS.serviceModes.enabled

  const defaultServiceModeCandidate = normalizeServiceMode(effective?.service_modes?.default)
  const defaultServiceMode = enabledModes.includes(defaultServiceModeCandidate)
    ? defaultServiceModeCandidate
    : enabledModes[0] || RUNTIME_DEFAULTS.serviceModes.default

  const idleTimeoutSeconds = clamp(
    Number(effective.idle_timeout_seconds || RUNTIME_DEFAULTS.idleTimeoutSeconds),
    10,
    600
  )

  const kitchenWarningRatio = clamp(
    Number(effective?.kitchen?.warning_ratio ?? RUNTIME_DEFAULTS.kitchenWarningRatio),
    0.1,
    0.95
  )

  const readyVisibilitySeconds = clamp(
    Number(effective?.display?.ready_visibility_seconds || RUNTIME_DEFAULTS.displayReadyVisibilitySeconds),
    30,
    1800
  )

  return {
    languages,
    defaultLanguage,
    idleTimeoutSeconds,
    kitchenWarningRatio,
    displayReadyVisibilitySeconds: readyVisibilitySeconds,
    serviceModes: {
      enabled: enabledModes,
      default: defaultServiceMode
    }
  }
}

export function getRuntimeDefaults() {
  return RUNTIME_DEFAULTS
}
