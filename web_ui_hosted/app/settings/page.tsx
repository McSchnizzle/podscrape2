'use client'

import { useState, useEffect, type ReactNode, type ChangeEvent } from 'react'
import {
  Loader2,
  AlertTriangle,
  CheckCircle2,
  RotateCcw,
  Save,
  Filter,
  Layers,
  GitBranch,
  Volume2,
  Gauge,
  Sparkles,
  Tag,
  Mic,
  FileAudio,
  Compass,
  TrendingUp,
  ShieldAlert,
  FileText,
  Trash2,
  Database,
  Timer,
  Search,
  Settings as SettingsIcon,
} from 'lucide-react'
import { toast } from '@/components/Toast'
import { PageHeader } from '@/components/ui/PageHeader'
import { Pill } from '@/components/ui/Pill'
import {
  SettingMeta,
  SettingValue
} from '@/lib/settings-keys'

interface Section {
  id: string
  label: string
  categories: string[]
}

interface SectionValidation {
  validCount: number
  warningCount: number
  errorCount: number
  hasChanges: boolean
  lastSaved: string | null  // ISO timestamp of most recent save in section
}

interface SettingsMeta {
  [category: string]: {
    [key: string]: {
      updated_at: string | null
    }
  }
}

const SECTIONS: Section[] = [
  { id: 'content', label: 'Content Filtering', categories: ['content_filtering'] },
  { id: 'dedup', label: 'Dedup Pass', categories: ['dedup'] },
  { id: 'pipeline', label: 'Pipeline', categories: ['pipeline'] },
  { id: 'audio', label: 'Audio Processing', categories: ['audio_processing'] },
  { id: 'ai-scoring', label: 'AI Content Scoring', categories: ['ai_content_scoring'] },
  { id: 'ai-digest', label: 'AI Digest Generation', categories: ['ai_digest_generation'] },
  { id: 'ai-metadata', label: 'AI Metadata', categories: ['ai_metadata_generation'] },
  { id: 'ai-tts', label: 'AI TTS', categories: ['ai_tts_generation'] },
  { id: 'ai-stt', label: 'AI STT', categories: ['ai_stt_transcription'] },
  { id: 'topic-tracking', label: 'Topic Tracking', categories: ['topic_tracking'] },
  { id: 'topic-evolution', label: 'Topic Evolution', categories: ['topic_evolution'] },
  { id: 'ad-filtering', label: 'Ad Filtering', categories: ['ad_filtering'] },
  { id: 'transcript', label: 'Transcript Processing', categories: ['transcript_processing'] },
  { id: 'retention', label: 'Retention', categories: ['retention'] },
  { id: 'database', label: 'Database', categories: ['database'] },
  { id: 'api-timeouts', label: 'API Timeouts', categories: ['api_timeouts'] },
  { id: 'tts', label: 'TTS', categories: ['tts'] },
  { id: 'discovery', label: 'Discovery', categories: ['discovery'] },
]

// Icon per section id, shared between the jump-nav and each section card header.
const SECTION_ICONS: Record<string, typeof Filter> = {
  content: Filter,
  dedup: Layers,
  pipeline: GitBranch,
  audio: Volume2,
  'ai-scoring': Gauge,
  'ai-digest': Sparkles,
  'ai-metadata': Tag,
  'ai-tts': Mic,
  'ai-stt': FileAudio,
  'topic-tracking': Compass,
  'topic-evolution': TrendingUp,
  'ad-filtering': ShieldAlert,
  transcript: FileText,
  retention: Trash2,
  database: Database,
  'api-timeouts': Timer,
  tts: Volume2,
  discovery: Search,
}

// ---------- shared field primitives (presentation only -- callers own all state/handlers) ----------

function NumberField({
  id,
  label,
  hint,
  value,
  onChange,
  min,
  max,
  step,
  disabled,
}: {
  id: string
  label: string
  hint?: ReactNode
  value: number
  onChange: (e: ChangeEvent<HTMLInputElement>) => void
  min?: number
  max?: number
  step?: number
  disabled?: boolean
}) {
  return (
    <div>
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        type="number"
        min={min}
        max={max}
        step={step}
        className="input"
        value={value}
        onChange={onChange}
        disabled={disabled}
      />
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  )
}

function SelectField({
  id,
  label,
  hint,
  value,
  onChange,
  disabled,
  children,
}: {
  id: string
  label: string
  hint?: ReactNode
  value: string
  onChange: (e: ChangeEvent<HTMLSelectElement>) => void
  disabled?: boolean
  children: ReactNode
}) {
  return (
    <div>
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <select id={id} className="select" value={value} onChange={onChange} disabled={disabled}>
        {children}
      </select>
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  )
}

function CheckboxField({
  id,
  label,
  checked,
  onChange,
  disabled,
}: {
  id: string
  label: ReactNode
  checked: boolean
  onChange: (e: ChangeEvent<HTMLInputElement>) => void
  disabled?: boolean
}) {
  return (
    <label
      htmlFor={id}
      className="flex items-center gap-[var(--space-2)] text-ink"
      style={{ font: 'var(--t-small)' }}
    >
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="h-4 w-4 accent-[var(--accent)]"
      />
      {label}
    </label>
  )
}

function InfoNote({ children }: { children: ReactNode }) {
  return (
    <div
      className="rounded-sm px-[var(--space-4)] py-[var(--space-3)]"
      style={{ background: 'var(--accent-soft)', color: 'var(--accent)', font: 'var(--t-small)' }}
    >
      {children}
    </div>
  )
}

function SectionCard({
  id,
  title,
  icon: Icon,
  description,
  children,
}: {
  id: string
  title: string
  icon?: typeof Filter
  description?: ReactNode
  children: ReactNode
}) {
  return (
    <div id={id} className="scroll-mt-24">
      <div className="card">
        <div className="flex items-center gap-[var(--space-3)]">
          {Icon && (
            <span
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-sm"
              style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}
              aria-hidden
            >
              <Icon size={16} />
            </span>
          )}
          <h3 style={{ font: 'var(--t-h3)', color: 'var(--text)' }}>{title}</h3>
        </div>
        {description && (
          <p className="mt-[var(--space-3)] text-ink-muted" style={{ font: 'var(--t-body)' }}>
            {description}
          </p>
        )}
        <div className="mt-[var(--space-5)] flex flex-col gap-[var(--space-4)]">{children}</div>
      </div>
    </div>
  )
}

function Subsection({
  title,
  description,
  divider = true,
  children,
}: {
  title: string
  description?: ReactNode
  divider?: boolean
  children: ReactNode
}) {
  return (
    <div
      className={
        divider
          ? 'flex flex-col gap-[var(--space-4)] border-t border-border pt-[var(--space-5)]'
          : 'flex flex-col gap-[var(--space-4)]'
      }
    >
      <div>
        <h4 className="micro">{title}</h4>
        {description && <p className="field-hint mt-[var(--space-1)]">{description}</p>}
      </div>
      {children}
    </div>
  )
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Record<string, Record<string, SettingValue>>>({})
  const [originalSettings, setOriginalSettings] = useState<Record<string, Record<string, SettingValue>>>({})
  const [schema, setSchema] = useState<Record<string, Record<string, SettingMeta>>>({})
  const [aiModels, setAiModels] = useState<Record<string, Record<string, { display_name: string }>>>({})
  const [schemaLoaded, setSchemaLoaded] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [activeSection, setActiveSection] = useState<string>('content')
  const [settingsMeta, setSettingsMeta] = useState<SettingsMeta>({})

  useEffect(() => {
    // Fetch both schema and settings in parallel
    const fetchAll = async () => {
      try {
        const [schemaResponse, settingsResponse] = await Promise.all([
          fetch('/api/settings/schema'),
          fetch('/api/settings')
        ])

        // Process schema
        if (schemaResponse.ok) {
          const schemaData = await schemaResponse.json()
          if (schemaData.settings) {
            setSchema(schemaData.settings)
            setSchemaLoaded(true)
          }
          if (schemaData.ai_models) {
            setAiModels(schemaData.ai_models)
          }
        } else {
          console.error('Failed to fetch settings schema')
        }

        // Process settings
        if (settingsResponse.ok) {
          const settingsData = await settingsResponse.json()
          setSettings(settingsData.settings || {})
          setOriginalSettings(settingsData.settings || {})
          setSettingsMeta(settingsData.settingsMeta || {})
        } else {
          const data = await settingsResponse.json()
          setMessage({ type: 'error', text: data.error || 'Failed to load settings' })
        }
      } catch (error) {
        setMessage({ type: 'error', text: 'Failed to connect to settings API' })
      } finally {
        setLoading(false)
      }
    }

    fetchAll()
  }, [])

  useEffect(() => {
    // Set up intersection observer to track which section is in view
    const observerOptions = {
      root: null,
      rootMargin: '-100px 0px -66%', // Trigger when section is near top
      threshold: 0
    }

    const observerCallback: IntersectionObserverCallback = (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          setActiveSection(entry.target.id)
        }
      })
    }

    const observer = new IntersectionObserver(observerCallback, observerOptions)

    // Observe all section elements
    SECTIONS.forEach((section) => {
      const element = document.getElementById(section.id)
      if (element) {
        observer.observe(element)
      }
    })

    return () => observer.disconnect()
  }, [schemaLoaded]) // Re-run when schema loads and sections render

  const updateLocalSetting = (category: string, key: string, value: SettingValue) => {
    setSettings(prev => ({
      ...prev,
      [category]: {
        ...prev[category],
        [key]: value
      }
    }))
    setHasChanges(true)
  }

  const saveAllSettings = async () => {
    setSaving(true)
    setMessage(null)

    try {
      const savePromises = []

      // Compare settings with original and save only changed ones
      for (const [category, categorySettings] of Object.entries(settings)) {
        for (const [key, value] of Object.entries(categorySettings)) {
          const originalValue = originalSettings[category]?.[key]
          if (JSON.stringify(value) !== JSON.stringify(originalValue)) {
            savePromises.push(
              fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category, key, value })
              })
            )
          }
        }
      }

      if (savePromises.length === 0) {
        setMessage({ type: 'error', text: 'No changes to save' })
        setSaving(false)
        return
      }

      const responses = await Promise.all(savePromises)
      const failed = responses.filter(r => !r.ok)

      if (failed.length === 0) {
        setOriginalSettings(settings)
        setHasChanges(false)
        setMessage({ type: 'success', text: `Saved ${savePromises.length} setting${savePromises.length > 1 ? 's' : ''} successfully` })
        setTimeout(() => setMessage(null), 3000)
      } else {
        setMessage({ type: 'error', text: `Failed to save ${failed.length} setting${failed.length > 1 ? 's' : ''}` })
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to save settings' })
    } finally {
      setSaving(false)
    }
  }

  const resetSettings = () => {
    setSettings(originalSettings)
    setHasChanges(false)
    setMessage(null)
  }

  const scrollToSection = (sectionId: string) => {
    const element = document.getElementById(sectionId)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'start' })
      setActiveSection(sectionId)
    }
  }

  const getChangedSettingsCount = (): number => {
    let count = 0
    for (const [category, categorySettings] of Object.entries(settings)) {
      for (const [key, value] of Object.entries(categorySettings)) {
        const originalValue = originalSettings[category]?.[key]
        if (JSON.stringify(value) !== JSON.stringify(originalValue)) {
          count++
        }
      }
    }
    return count
  }

  const getSectionValidation = (section: Section): SectionValidation => {
    let validCount = 0
    let warningCount = 0
    let errorCount = 0
    let hasChanges = false
    let latestTimestamp: string | null = null

    for (const category of section.categories) {
      const categorySettings = settings[category] || {}
      const categorySchema = schema[category] || {}
      const categoryMeta = settingsMeta[category] || {}
      const originalCategorySettings = originalSettings[category] || {}

      for (const [key, value] of Object.entries(categorySettings)) {
        const settingSchema = categorySchema[key]
        const settingMeta = categoryMeta[key]

        // Check for changes
        const originalValue = originalCategorySettings[key]
        if (JSON.stringify(value) !== JSON.stringify(originalValue)) {
          hasChanges = true
        }

        // Track latest timestamp
        if (settingMeta?.updated_at) {
          if (!latestTimestamp || settingMeta.updated_at > latestTimestamp) {
            latestTimestamp = settingMeta.updated_at
          }
        }

        // Validate against schema constraints
        if (settingSchema) {
          let isValid = true

          if (settingSchema.type === 'int' || settingSchema.type === 'float') {
            const numValue = Number(value)
            if (settingSchema.min !== null && settingSchema.min !== undefined && numValue < settingSchema.min) {
              isValid = false
            }
            if (settingSchema.max !== null && settingSchema.max !== undefined && numValue > settingSchema.max) {
              isValid = false
            }
          }

          if (!isValid) {
            errorCount++
          } else {
            validCount++
          }
        } else {
          validCount++ // No schema means no constraints violated
        }
      }
    }

    return {
      validCount,
      warningCount,
      errorCount,
      hasChanges,
      lastSaved: latestTimestamp
    }
  }

  const formatRelativeTime = (timestamp: string | null): string | null => {
    if (!timestamp) return null

    const date = new Date(timestamp)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / (1000 * 60))
    const hours = Math.floor(diff / (1000 * 60 * 60))
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))

    if (minutes < 1) return 'just now'
    if (minutes < 60) return `${minutes}m ago`
    if (hours < 24) return `${hours}h ago`
    if (days < 7) return `${days}d ago`
    return date.toLocaleDateString()
  }

  // Get setting value, falling back to schema default
  const getSetting = (category: string, key: string): SettingValue => {
    const value = settings[category]?.[key]
    if (value !== undefined && value !== null) {
      return value
    }
    // Use schema default instead of hardcoded fallback
    const schemaDefault = schema[category]?.[key]?.default
    if (schemaDefault !== undefined) {
      return schemaDefault
    }
    // If schema not loaded yet, return a safe default based on type
    return 0
  }

  // Type-safe getters for specific value types
  const getSettingNumber = (category: string, key: string): number => {
    const value = getSetting(category, key)
    return typeof value === 'number' ? value : Number(value)
  }

  const getSettingString = (category: string, key: string): string => {
    const value = getSetting(category, key)
    return String(value)
  }

  const getSettingBoolean = (category: string, key: string): boolean => {
    const value = getSetting(category, key)
    return typeof value === 'boolean' ? value : Boolean(value)
  }

  // Get min/max constraints from schema for input validation
  const getMinMax = (category: string, key: string) => {
    const meta = schema[category]?.[key]
    return {
      min: meta?.min ?? 0,
      max: meta?.max ?? 99999
    }
  }

  // Render model options from aiModels data
  const renderModelOptions = (provider: string) => {
    const models = aiModels[provider]
    if (!models) return null
    return Object.entries(models).map(([modelId, info]) => (
      <option key={modelId} value={modelId}>{info.display_name}</option>
    ))
  }

  if (loading || !schemaLoaded) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <div className="flex items-center gap-[var(--space-2)] text-ink-subtle" style={{ font: 'var(--t-body)' }}>
          <Loader2 size={18} className="animate-spin" />
          Loading settings…
        </div>
      </div>
    )
  }

  return (
    <div>
      <PageHeader title="Settings" description="Configure system parameters and processing options" />

      {message && (
        <div
          className="mb-[var(--space-6)] flex items-center gap-[var(--space-2)] rounded-sm px-[var(--space-4)] py-[var(--space-3)]"
          style={{
            background: message.type === 'success' ? 'var(--success-soft)' : 'var(--danger-soft)',
            color: message.type === 'success' ? 'var(--success)' : 'var(--danger)',
            font: 'var(--t-small)',
          }}
        >
          {message.type === 'success' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          {message.text}
        </div>
      )}

      <div className="flex flex-col gap-[var(--space-6)] lg:flex-row lg:items-start">
        {/* Left sidebar navigation */}
        <nav className="hidden shrink-0 lg:block lg:w-64">
          <div className="sticky top-[var(--space-6)] flex flex-col gap-[2px]">
            <div className="micro mb-[var(--space-2)] px-[var(--space-3)]">Jump to section</div>
            {SECTIONS.map((section) => {
              const validation = getSectionValidation(section)
              const lastSavedText = formatRelativeTime(validation.lastSaved)
              const active = activeSection === section.id
              const Icon = SECTION_ICONS[section.id] || SettingsIcon

              return (
                <button
                  key={section.id}
                  onClick={() => scrollToSection(section.id)}
                  className={`w-full rounded-sm px-[var(--space-3)] py-[var(--space-2)] text-left transition-colors duration-fast ease-house ${
                    active ? 'bg-accent-soft text-accent' : 'text-ink-muted hover:bg-surface-2 hover:text-ink'
                  }`}
                >
                  <div className="flex items-center justify-between gap-[var(--space-2)]">
                    <span
                      className="flex min-w-0 items-center gap-[var(--space-2)] truncate"
                      style={{ font: 'var(--t-small)', fontWeight: active ? 600 : 500 }}
                    >
                      <Icon size={14} className={active ? 'shrink-0 text-accent' : 'shrink-0 text-ink-faint'} />
                      <span className="truncate">{section.label}</span>
                    </span>
                    <div className="flex shrink-0 items-center gap-[6px]">
                      {validation.hasChanges && (
                        <span
                          className="h-2 w-2 rounded-full"
                          style={{ background: 'var(--warning)' }}
                          title="Unsaved changes"
                        />
                      )}
                      {validation.errorCount > 0 ? (
                        <Pill tone="danger">{validation.errorCount}</Pill>
                      ) : (
                        validation.validCount > 0 && <Pill tone="success">{validation.validCount}</Pill>
                      )}
                    </div>
                  </div>
                  {lastSavedText && (
                    <div className="mt-[2px] pl-[22px] text-ink-faint" style={{ font: 'var(--t-micro)' }}>
                      Saved {lastSavedText}
                    </div>
                  )}
                </button>
              )
            })}
          </div>
        </nav>

        {/* Main content area */}
        <div className="min-w-0 flex-1 pb-[var(--space-9)]">
          <div className="flex flex-col gap-[var(--space-7)]">
            <SectionCard id="content" title="Content Filtering" icon={Filter}>
              <NumberField
                id="content_filtering-score_threshold"
                label="Score Threshold"
                hint="Minimum relevance score for episodes (0.0 - 1.0)"
                step={0.01}
                min={0}
                max={1}
                value={getSettingNumber('content_filtering', 'score_threshold')}
                onChange={(e) => updateLocalSetting('content_filtering', 'score_threshold', parseFloat(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="content_filtering-max_episodes_per_digest"
                label="Starting Episode Pool Size"
                hint={
                  <>
                    Number of highest-scoring episodes used to generate the initial draft.
                    If the post-dedup script is below the target floor (see Dedup Pass settings),
                    the pipeline will pull additional scored episodes and regenerate.
                  </>
                }
                min={1}
                max={20}
                value={getSettingNumber('content_filtering', 'max_episodes_per_digest')}
                onChange={(e) => updateLocalSetting('content_filtering', 'max_episodes_per_digest', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="content_filtering-min_episodes_per_digest"
                label="Min Episodes per Digest"
                hint="Minimum episodes required to generate a digest (0 = always generate)"
                min={0}
                max={10}
                value={getSettingNumber('content_filtering', 'min_episodes_per_digest')}
                onChange={(e) => updateLocalSetting('content_filtering', 'min_episodes_per_digest', parseInt(e.target.value))}
                disabled={saving}
              />
            </SectionCard>

            <SectionCard
              id="dedup"
              title="Dedup Pass"
              icon={Layers}
              description={
                <>
                  After the script is generated, a <code>claude -p</code> pass compares
                  the draft against the last N digests and rewrites repeated story beats
                  as one-line &quot;quick updates.&quot; If the post-dedup script is below the
                  target floor, the pipeline pulls more scored episodes and regenerates.
                </>
              }
            >
              <CheckboxField
                id="dedup_enabled"
                label="Enable post-generation dedup pass"
                checked={getSettingBoolean('dedup', 'enabled')}
                onChange={(e) => updateLocalSetting('dedup', 'enabled', e.target.checked)}
                disabled={saving}
              />
              <NumberField
                id="dedup-lookback_digests"
                label="Lookback Digests"
                hint="Number of prior digests the dedup pass compares against (default 8)."
                min={1}
                max={30}
                value={getSettingNumber('dedup', 'lookback_digests')}
                onChange={(e) => updateLocalSetting('dedup', 'lookback_digests', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="dedup-target_chars_floor"
                label="Target Character Floor"
                hint={
                  <>
                    Minimum character count for the <em>final</em> (post-dedup) script.
                    If the deduped draft falls below this, the pipeline adds one more
                    scored episode and regenerates. Default 20,000.
                  </>
                }
                min={5000}
                max={60000}
                step={1000}
                value={getSettingNumber('dedup', 'target_chars_floor')}
                onChange={(e) => updateLocalSetting('dedup', 'target_chars_floor', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="dedup-max_expansion_episodes"
                label="Max Expansion Episodes"
                hint={
                  <>
                    Hard cap on how many <em>extra</em> episodes the expansion loop may
                    add beyond the Starting Episode Pool Size. Default 5.
                  </>
                }
                min={0}
                max={15}
                value={getSettingNumber('dedup', 'max_expansion_episodes')}
                onChange={(e) => updateLocalSetting('dedup', 'max_expansion_episodes', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="dedup-max_iterations"
                label="Max Iterations"
                hint="Safety cap on the dedup-and-expand loop. Default 5."
                min={1}
                max={10}
                value={getSettingNumber('dedup', 'max_iterations')}
                onChange={(e) => updateLocalSetting('dedup', 'max_iterations', parseInt(e.target.value))}
                disabled={saving}
              />
              <div>
                <CheckboxField
                  id="dedup_scrub"
                  label="Scrub saturated-topic content from transcripts before each regeneration"
                  checked={getSettingBoolean('dedup', 'scrub_transcripts_on_regen')}
                  onChange={(e) => updateLocalSetting('dedup', 'scrub_transcripts_on_regen', e.target.checked)}
                  disabled={saving}
                />
                <p className="field-hint pl-[var(--space-5)]">
                  Before regenerating with expanded episodes, run a <code>claude -p</code>{' '}
                  pass over each transcript to remove sentences discussing already-saturated
                  stories. Prevents the new draft from re-introducing content dedup just cut.
                </p>
              </div>
            </SectionCard>

            <SectionCard id="pipeline" title="Pipeline" icon={GitBranch}>
              <NumberField
                id="pipeline-max_episodes_per_run"
                label="Max Episodes per Run"
                min={1}
                max={20}
                value={getSettingNumber('pipeline', 'max_episodes_per_run')}
                onChange={(e) => updateLocalSetting('pipeline', 'max_episodes_per_run', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="pipeline-discovery_lookback_days"
                label="Days Back for Discovery"
                hint="Number of days to look back when discovering new episodes"
                min={1}
                max={30}
                value={getSettingNumber('pipeline', 'discovery_lookback_days')}
                onChange={(e) => {
                  const newValue = parseInt(e.target.value)
                  updateLocalSetting('pipeline', 'discovery_lookback_days', newValue)
                  // Auto-adjust episode retention if needed
                  const currentRetention = getSettingNumber('retention', 'episode_retention_days')
                  if (newValue >= currentRetention) {
                    updateLocalSetting('retention', 'episode_retention_days', newValue + 1)
                  }
                }}
                disabled={saving}
              />
            </SectionCard>

            <SectionCard id="audio" title="Audio Processing" icon={Volume2}>
              <NumberField
                id="audio_processing-chunk_duration_minutes"
                label="Chunk Duration (minutes)"
                min={1}
                max={30}
                value={getSettingNumber('audio_processing', 'chunk_duration_minutes')}
                onChange={(e) => updateLocalSetting('audio_processing', 'chunk_duration_minutes', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="audio_processing-max_chunks_per_episode"
                label="Max Chunks per Episode"
                min={1}
                max={10}
                value={getSettingNumber('audio_processing', 'max_chunks_per_episode')}
                onChange={(e) => updateLocalSetting('audio_processing', 'max_chunks_per_episode', parseInt(e.target.value))}
                disabled={saving}
              />
              <CheckboxField
                id="transcribe-all-chunks"
                label="Transcribe all chunks"
                checked={getSettingBoolean('audio_processing', 'transcribe_all_chunks')}
                onChange={(e) => updateLocalSetting('audio_processing', 'transcribe_all_chunks', e.target.checked)}
                disabled={saving}
              />
            </SectionCard>

            <SectionCard id="ai-scoring" title="AI Content Scoring" icon={Gauge}>
              <SelectField
                id="ai_content_scoring-model"
                label="Model"
                value={getSettingString('ai_content_scoring', 'model')}
                onChange={(e) => updateLocalSetting('ai_content_scoring', 'model', e.target.value)}
                disabled={saving}
              >
                {renderModelOptions('openai')}
              </SelectField>
              <NumberField
                id="ai_content_scoring-max_tokens"
                label="Max Output Tokens"
                min={100}
                max={4000}
                value={getSettingNumber('ai_content_scoring', 'max_tokens')}
                onChange={(e) => updateLocalSetting('ai_content_scoring', 'max_tokens', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="ai_content_scoring-max_input_tokens"
                label="Max Input Tokens"
                min={1000}
                max={200000}
                value={getSettingNumber('ai_content_scoring', 'max_input_tokens')}
                onChange={(e) => updateLocalSetting('ai_content_scoring', 'max_input_tokens', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="ai_content_scoring-max_episodes_per_batch"
                label="Max Episodes per Batch"
                min={1}
                max={20}
                value={getSettingNumber('ai_content_scoring', 'max_episodes_per_batch')}
                onChange={(e) => updateLocalSetting('ai_content_scoring', 'max_episodes_per_batch', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="ai_content_scoring-prompt_max_chars"
                label="Prompt Max Characters"
                hint="Maximum characters to include from topic prompt in scoring context"
                min={0}
                max={200000}
                value={getSettingNumber('ai_content_scoring', 'prompt_max_chars')}
                onChange={(e) => updateLocalSetting('ai_content_scoring', 'prompt_max_chars', parseInt(e.target.value))}
                disabled={saving}
              />
            </SectionCard>

            <SectionCard id="ai-digest" title="AI Digest Generation" icon={Sparkles}>
              <SelectField
                id="ai_digest_generation-model"
                label="Model"
                value={getSettingString('ai_digest_generation', 'model')}
                onChange={(e) => updateLocalSetting('ai_digest_generation', 'model', e.target.value)}
                disabled={saving}
              >
                <optgroup label="OpenAI">{renderModelOptions('openai')}</optgroup>
                <optgroup label="Anthropic">{renderModelOptions('anthropic')}</optgroup>
              </SelectField>
              <NumberField
                id="ai_digest_generation-max_output_tokens"
                label="Max Output Tokens"
                min={1000}
                max={50000}
                value={getSettingNumber('ai_digest_generation', 'max_output_tokens')}
                onChange={(e) => updateLocalSetting('ai_digest_generation', 'max_output_tokens', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="ai_digest_generation-max_input_tokens"
                label="Max Input Tokens"
                min={1000}
                max={200000}
                value={getSettingNumber('ai_digest_generation', 'max_input_tokens')}
                onChange={(e) => updateLocalSetting('ai_digest_generation', 'max_input_tokens', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="ai_digest_generation-transcript_buffer_percent"
                label="Transcript Buffer (%)"
                hint="Buffer percentage for transcript token calculations"
                step={0.1}
                min={0}
                max={50}
                value={getSettingNumber('ai_digest_generation', 'transcript_buffer_percent')}
                onChange={(e) => updateLocalSetting('ai_digest_generation', 'transcript_buffer_percent', parseFloat(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="ai_digest_generation-transcript_min_chars"
                label="Transcript Min Characters"
                hint="Minimum transcript characters required per episode (0-500,000)"
                min={0}
                max={500000}
                value={getSettingNumber('ai_digest_generation', 'transcript_min_chars')}
                onChange={(e) => updateLocalSetting('ai_digest_generation', 'transcript_min_chars', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="ai_digest_generation-transcript_max_chars"
                label="Transcript Max Characters"
                hint="Max transcript chars per episode sent to AI (0-1,000,000). Use 200,000+ for full transcripts with no truncation."
                min={0}
                max={1000000}
                value={getSettingNumber('ai_digest_generation', 'transcript_max_chars')}
                onChange={(e) => updateLocalSetting('ai_digest_generation', 'transcript_max_chars', parseInt(e.target.value))}
                disabled={saving}
              />
            </SectionCard>

            <SectionCard id="ai-metadata" title="AI Metadata Generation" icon={Tag}>
              <SelectField
                id="ai_metadata_generation-model"
                label="Model"
                value={getSettingString('ai_metadata_generation', 'model')}
                onChange={(e) => updateLocalSetting('ai_metadata_generation', 'model', e.target.value)}
                disabled={saving}
              >
                {renderModelOptions('openai')}
              </SelectField>
              <NumberField
                id="ai_metadata_generation-max_input_tokens"
                label="Max Input Tokens"
                hint="Maximum input tokens for metadata generation context"
                min={1000}
                max={128000}
                value={getSettingNumber('ai_metadata_generation', 'max_input_tokens')}
                onChange={(e) => updateLocalSetting('ai_metadata_generation', 'max_input_tokens', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="ai_metadata_generation-max_title_tokens"
                label="Max Title Tokens"
                min={10}
                max={100}
                value={getSettingNumber('ai_metadata_generation', 'max_title_tokens')}
                onChange={(e) => updateLocalSetting('ai_metadata_generation', 'max_title_tokens', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="ai_metadata_generation-max_summary_tokens"
                label="Max Summary Tokens"
                min={50}
                max={500}
                value={getSettingNumber('ai_metadata_generation', 'max_summary_tokens')}
                onChange={(e) => updateLocalSetting('ai_metadata_generation', 'max_summary_tokens', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="ai_metadata_generation-max_description_tokens"
                label="Max Description Tokens"
                min={100}
                max={1000}
                value={getSettingNumber('ai_metadata_generation', 'max_description_tokens')}
                onChange={(e) => updateLocalSetting('ai_metadata_generation', 'max_description_tokens', parseInt(e.target.value))}
                disabled={saving}
              />
            </SectionCard>

            <SectionCard id="ai-tts" title="AI TTS Generation" icon={Mic}>
              <SelectField
                id="ai_tts_generation-model"
                label="Model"
                value={getSettingString('ai_tts_generation', 'model')}
                onChange={(e) => updateLocalSetting('ai_tts_generation', 'model', e.target.value)}
                disabled={saving}
              >
                {renderModelOptions('elevenlabs')}
              </SelectField>
              <NumberField
                id="ai_tts_generation-max_characters"
                label="Max Characters"
                hint="Maximum characters per TTS generation"
                min={1000}
                max={50000}
                value={getSettingNumber('ai_tts_generation', 'max_characters')}
                onChange={(e) => updateLocalSetting('ai_tts_generation', 'max_characters', parseInt(e.target.value))}
                disabled={saving}
              />
            </SectionCard>

            <SectionCard id="ai-stt" title="AI STT Transcription" icon={FileAudio}>
              <SelectField
                id="ai_stt_transcription-model"
                label="Model"
                value={getSettingString('ai_stt_transcription', 'model')}
                onChange={(e) => updateLocalSetting('ai_stt_transcription', 'model', e.target.value)}
                disabled={saving}
              >
                <option value="whisper-1">Whisper-1</option>
                <option value="local-whisper">Local Whisper</option>
              </SelectField>
              <NumberField
                id="ai_stt_transcription-max_file_size_mb"
                label="Max File Size (MB)"
                min={1}
                max={100}
                value={getSettingNumber('ai_stt_transcription', 'max_file_size_mb')}
                onChange={(e) => updateLocalSetting('ai_stt_transcription', 'max_file_size_mb', parseInt(e.target.value))}
                disabled={saving}
              />
            </SectionCard>

            <SectionCard id="topic-tracking" title="Topic Tracking" icon={Compass}>
              <SelectField
                id="topic_tracking-extraction_model"
                label="Extraction Model"
                hint="Model used for extracting topics from transcripts"
                value={getSettingString('topic_tracking', 'extraction_model')}
                onChange={(e) => updateLocalSetting('topic_tracking', 'extraction_model', e.target.value)}
                disabled={saving}
              >
                {renderModelOptions('openai')}
              </SelectField>
              <NumberField
                id="topic_tracking-min_score_for_extraction"
                label="Min Score for Extraction"
                hint="Minimum episode score required to extract topics (0.0 - 1.0)"
                step={0.01}
                min={0}
                max={1}
                value={getSettingNumber('topic_tracking', 'min_score_for_extraction')}
                onChange={(e) => updateLocalSetting('topic_tracking', 'min_score_for_extraction', parseFloat(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="topic_tracking-max_topics_per_episode"
                label="Max Topics per Episode"
                hint="Maximum number of topics to extract per episode"
                min={3}
                max={20}
                value={getSettingNumber('topic_tracking', 'max_topics_per_episode')}
                onChange={(e) => updateLocalSetting('topic_tracking', 'max_topics_per_episode', parseInt(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="topic_tracking-retention_days"
                label="Retention Days (Deduplication Window)"
                hint="Number of days to look back for duplicate topic detection"
                min={7}
                max={90}
                value={getSettingNumber('topic_tracking', 'retention_days')}
                onChange={(e) => updateLocalSetting('topic_tracking', 'retention_days', parseInt(e.target.value))}
                disabled={saving}
              />

              <Subsection
                title="Digest Reconciliation"
                description="After digest generation, analyze recent scripts to detect recurring stories not yet tracked as arcs."
              >
                <SelectField
                  id="topic_tracking-reconciliation_model"
                  label="Reconciliation Model"
                  hint="GPT model used for detecting recurring stories across digests"
                  value={getSettingString('topic_tracking', 'reconciliation_model')}
                  onChange={(e) => updateLocalSetting('topic_tracking', 'reconciliation_model', e.target.value)}
                  disabled={saving}
                >
                  {renderModelOptions('openai')}
                </SelectField>
                <NumberField
                  id="topic_tracking-reconciliation_lookback"
                  label="Reconciliation Lookback (digests)"
                  hint="Number of recent digests to analyze for recurring stories"
                  min={3}
                  max={15}
                  value={getSettingNumber('topic_tracking', 'reconciliation_lookback')}
                  onChange={(e) => updateLocalSetting('topic_tracking', 'reconciliation_lookback', parseInt(e.target.value))}
                  disabled={saving}
                />
                <NumberField
                  id="topic_tracking-reconciliation_min_occurrences"
                  label="Min Occurrences"
                  hint="Minimum digest appearances required to create a story arc"
                  min={2}
                  max={5}
                  value={getSettingNumber('topic_tracking', 'reconciliation_min_occurrences')}
                  onChange={(e) => updateLocalSetting('topic_tracking', 'reconciliation_min_occurrences', parseInt(e.target.value))}
                  disabled={saving}
                />
              </Subsection>
            </SectionCard>

            <SectionCard id="ad-filtering" title="Ad Filtering" icon={ShieldAlert}>
              <CheckboxField
                id="ad-filtering-enabled"
                label="Enable ad filtering"
                checked={getSettingBoolean('ad_filtering', 'enabled')}
                onChange={(e) => updateLocalSetting('ad_filtering', 'enabled', e.target.checked)}
                disabled={saving}
              />
              <NumberField
                id="ad_filtering-confidence_threshold"
                label="Confidence Threshold"
                hint="Minimum confidence required to filter an ad (0.0 - 1.0, higher = stricter)"
                step={0.1}
                min={0}
                max={1}
                value={getSettingNumber('ad_filtering', 'confidence_threshold')}
                onChange={(e) => updateLocalSetting('ad_filtering', 'confidence_threshold', parseFloat(e.target.value))}
                disabled={saving}
              />
              <InfoNote>
                <strong>Note:</strong> Ad patterns are managed in the database. Enable topic tracking per topic to use deduplication.
              </InfoNote>
            </SectionCard>

            <SectionCard id="topic-evolution" title="Topic Evolution" icon={TrendingUp}>
              <CheckboxField
                id="enable-novelty-detection"
                label="Enable novelty detection"
                checked={getSettingBoolean('topic_evolution', 'enable_novelty_detection')}
                onChange={(e) => updateLocalSetting('topic_evolution', 'enable_novelty_detection', e.target.checked)}
                disabled={saving}
              />
              <NumberField
                id="topic_evolution-novelty_threshold"
                label="Novelty Threshold"
                hint="Minimum novelty required to include topic (0.0-1.0, lower = more lenient)"
                step={0.05}
                min={0}
                max={1}
                value={getSettingNumber('topic_evolution', 'novelty_threshold')}
                onChange={(e) => updateLocalSetting('topic_evolution', 'novelty_threshold', parseFloat(e.target.value))}
                disabled={saving}
              />
              <SelectField
                id="topic_evolution-embedding_model"
                label="Embedding Model"
                hint="OpenAI embedding model for semantic similarity comparisons"
                value={getSettingString('topic_evolution', 'embedding_model')}
                onChange={(e) => updateLocalSetting('topic_evolution', 'embedding_model', e.target.value)}
                disabled={saving}
              >
                <option value="text-embedding-3-small">text-embedding-3-small (Fast, $0.02/1M)</option>
                <option value="text-embedding-3-large">text-embedding-3-large (Higher quality, $0.13/1M)</option>
              </SelectField>
              <NumberField
                id="topic_evolution-similarity_threshold"
                label="Similarity Threshold"
                hint="Minimum similarity score to consider topics as duplicates (0.5-1.0, higher = stricter matching)"
                step={0.05}
                min={0.5}
                max={1}
                value={getSettingNumber('topic_evolution', 'similarity_threshold')}
                onChange={(e) => updateLocalSetting('topic_evolution', 'similarity_threshold', parseFloat(e.target.value))}
                disabled={saving}
              />
              <InfoNote>
                <strong>Info:</strong> Novelty detection uses embeddings to compare topics and allow fresh content even if topic slugs
                match. Lower threshold = more likely to include topics with similar content.
              </InfoNote>
            </SectionCard>

            <SectionCard id="transcript" title="Transcript Processing" icon={FileText}>
              <CheckboxField
                id="ad-trim-enabled"
                label="Enable ad trimming"
                checked={getSettingBoolean('transcript_processing', 'ad_trim_enabled')}
                onChange={(e) => updateLocalSetting('transcript_processing', 'ad_trim_enabled', e.target.checked)}
                disabled={saving}
              />
              <NumberField
                id="transcript_processing-ad_trim_start_percent"
                label="Trim Start (%)"
                hint="Percentage of transcript to trim from start (for ads)"
                step={0.1}
                min={0}
                max={50}
                value={getSettingNumber('transcript_processing', 'ad_trim_start_percent')}
                onChange={(e) => updateLocalSetting('transcript_processing', 'ad_trim_start_percent', parseFloat(e.target.value))}
                disabled={saving}
              />
              <NumberField
                id="transcript_processing-ad_trim_end_percent"
                label="Trim End (%)"
                hint="Percentage of transcript to trim from end (for ads)"
                step={0.1}
                min={0}
                max={50}
                value={getSettingNumber('transcript_processing', 'ad_trim_end_percent')}
                onChange={(e) => updateLocalSetting('transcript_processing', 'ad_trim_end_percent', parseFloat(e.target.value))}
                disabled={saving}
              />
            </SectionCard>

            <SectionCard id="retention" title="Retention" icon={Trash2}>
              <Subsection title="Database Cleanup" divider={false}>
                <NumberField
                  id="retention-episode_retention_days"
                  label="Episode Retention (days)"
                  hint="Delete episodes from database older than this many days (must be greater than discovery lookback)"
                  min={1}
                  max={90}
                  value={getSettingNumber('retention', 'episode_retention_days')}
                  onChange={(e) => {
                    const newValue = parseInt(e.target.value)
                    const lookbackDays = getSettingNumber('pipeline', 'discovery_lookback_days')
                    if (newValue <= lookbackDays) {
                      toast.error('Validation Error', {
                        description: `Episode retention days must be greater than discovery lookback days (${lookbackDays})`,
                        duration: 6000
                      })
                      return
                    }
                    updateLocalSetting('retention', 'episode_retention_days', newValue)
                  }}
                  disabled={saving}
                />
                <NumberField
                  id="retention-digest_retention_days"
                  label="Digest Retention (days)"
                  hint="Delete digests from database older than this many days"
                  min={1}
                  max={90}
                  value={getSettingNumber('retention', 'digest_retention_days')}
                  onChange={(e) => updateLocalSetting('retention', 'digest_retention_days', parseInt(e.target.value))}
                  disabled={saving}
                />
              </Subsection>

              <Subsection title="File & Cache Cleanup">
                <NumberField
                  id="retention-local_mp3_days"
                  label="Local MP3s (days)"
                  hint="Delete local MP3 files older than this many days"
                  min={1}
                  max={90}
                  value={getSettingNumber('retention', 'local_mp3_days')}
                  onChange={(e) => updateLocalSetting('retention', 'local_mp3_days', parseInt(e.target.value))}
                  disabled={saving}
                />
                <NumberField
                  id="retention-audio_cache_days"
                  label="Audio Cache (days)"
                  hint="Delete cached audio files older than this many days"
                  min={1}
                  max={30}
                  value={getSettingNumber('retention', 'audio_cache_days')}
                  onChange={(e) => updateLocalSetting('retention', 'audio_cache_days', parseInt(e.target.value))}
                  disabled={saving}
                />
                <NumberField
                  id="retention-audio_chunks_days"
                  label="Audio Chunks (days)"
                  hint="Delete chunked audio files older than this many days"
                  min={0}
                  max={30}
                  value={getSettingNumber('retention', 'audio_chunks_days')}
                  onChange={(e) => updateLocalSetting('retention', 'audio_chunks_days', parseInt(e.target.value))}
                  disabled={saving}
                />
                <NumberField
                  id="retention-logs_days"
                  label="Logs (days)"
                  hint="Delete log files older than this many days"
                  min={1}
                  max={365}
                  value={getSettingNumber('retention', 'logs_days')}
                  onChange={(e) => updateLocalSetting('retention', 'logs_days', parseInt(e.target.value))}
                  disabled={saving}
                />
              </Subsection>

              <Subsection title="Publishing Cleanup">
                <NumberField
                  id="retention-github_releases_days"
                  label="GitHub Releases (days)"
                  hint="Delete GitHub releases older than this many days (0 = keep forever)"
                  min={0}
                  max={365}
                  value={getSettingNumber('retention', 'github_releases_days')}
                  onChange={(e) => updateLocalSetting('retention', 'github_releases_days', parseInt(e.target.value))}
                  disabled={saving}
                />
              </Subsection>
            </SectionCard>
          </div>
        </div>
      </div>

      {/* Sticky save bar */}
      {hasChanges && (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-surface-1 shadow-lg">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-[var(--space-4)] px-[var(--space-4)] py-[var(--space-3)] sm:px-[var(--space-6)] lg:px-[var(--space-7)]">
            <div className="flex items-center gap-[var(--space-3)]">
              <Pill tone="accent">{getChangedSettingsCount()}</Pill>
              <span className="text-ink-muted" style={{ font: 'var(--t-small)' }}>
                unsaved {getChangedSettingsCount() === 1 ? 'change' : 'changes'}
              </span>
            </div>
            <div className="flex items-center gap-[var(--space-3)]">
              <button onClick={resetSettings} disabled={saving} className="btn btn-secondary btn-sm">
                <RotateCcw size={13} /> Reset
              </button>
              <button onClick={saveAllSettings} disabled={saving} className="btn btn-primary btn-sm">
                {saving ? (
                  <>
                    <Loader2 size={13} className="animate-spin" /> Saving…
                  </>
                ) : (
                  <>
                    <Save size={13} /> Save changes
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Saving overlay indicator */}
      {saving && (
        <div
          className="fixed bottom-[var(--space-4)] right-[var(--space-4)] z-50 flex items-center gap-[var(--space-2)] rounded-sm px-[var(--space-4)] py-[var(--space-3)] shadow-lg"
          style={{ background: 'var(--accent)', color: 'var(--on-accent)', font: 'var(--t-small)' }}
        >
          <Loader2 size={14} className="animate-spin" />
          Saving…
        </div>
      )}
    </div>
  )
}
