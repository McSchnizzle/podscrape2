'use client';

import { useState, useEffect } from 'react';
import { AlertTriangle, Loader2, Sparkles, Save, Eye } from 'lucide-react';
import { PageHeader } from '@/components/ui/PageHeader';

interface Topic {
  name: string;
}

interface ScriptLabData {
  content: string;
  type_of_show: string;
  voice_label: string;
  tone: string;
  pace: string;
}

const typeOfShowOptions = ['newscast', 'dialog', 'narrative story', 'critical analysis'];
const voiceLabelOptions = ['American news anchor', 'British man', 'Black woman', 'energetic millennial'];
const toneOptions = ['neutral', 'inspirational', 'critical', 'investigative'];
const paceOptions = ['fast', 'moderate', 'reflective'];

export default function ScriptLabPage() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [selectedTopic, setSelectedTopic] = useState<string>('');
  const [scriptData, setScriptData] = useState<ScriptLabData>({
    content: '',
    type_of_show: 'newscast',
    voice_label: 'American news anchor',
    tone: 'neutral',
    pace: 'moderate'
  });
  const [preview, setPreview] = useState<string>('');
  const [previewStats, setPreviewStats] = useState<{
    char_count?: number;
    word_count?: number;
    episode_count?: number;
    mode?: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Load topics on mount
  useEffect(() => {
    const loadTopics = async () => {
      try {
        const response = await fetch('/api/topics');
        if (response.ok) {
          const payload = await response.json();
          const list: Topic[] = Array.isArray(payload)
            ? payload
            : Array.isArray(payload.topics)
              ? payload.topics.map((topic: any) => ({ name: topic.name }))
              : [];

          setTopics(list);
          if (list.length > 0 && !selectedTopic) {
            setSelectedTopic(list[0].name);
          }
        }
      } catch (error) {
        console.error('Failed to load topics:', error);
      }
    };
    loadTopics();
  }, []);

  // Load topic data when selection changes
  useEffect(() => {
    if (!selectedTopic) return;

    const loadTopicData = async () => {
      try {
        const response = await fetch(`/api/script-lab?topic=${encodeURIComponent(selectedTopic)}`);
        if (response.ok) {
          const data = await response.json();
          setScriptData(data);
          setPreview(''); // Clear preview when switching topics
        }
      } catch (error) {
        console.error('Failed to load topic data:', error);
      }
    };

    loadTopicData();
  }, [selectedTopic]);

  const updateScriptData = (field: keyof ScriptLabData, value: string) => {
    setScriptData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleAction = async (action: 'save' | 'rewrite' | 'preview') => {
    if (!selectedTopic) {
      setMessage({ type: 'error', text: 'No topic selected' });
      return;
    }

    setLoading(true);
    setMessage(null);

    try {
      const response = await fetch('/api/script-lab', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          action,
          topic: selectedTopic,
          ...scriptData
        }),
      });

      const data = await response.json();

      if (response.ok) {
        setMessage({ type: 'success', text: data.message || 'Operation completed successfully' });

        if (action === 'rewrite' && data.content) {
          setScriptData(prev => ({ ...prev, content: data.content }));
        } else if (action === 'preview' && data.preview) {
          setPreview(data.preview);
          setPreviewStats({
            char_count: data.char_count,
            word_count: data.word_count,
            episode_count: data.episode_count,
            mode: data.mode
          });
        }
      } else {
        setMessage({ type: 'error', text: data.error || 'Operation failed' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Failed to process request' });
    } finally {
      setLoading(false);
    }
  };

  if (topics.length === 0) {
    return (
      <div>
        <PageHeader title="Script Lab" description="Tune digest voice, tone, and pace per topic, then preview and save instructions." />
        <div
          className="flex items-center gap-[var(--space-2)] rounded-sm px-[var(--space-4)] py-[var(--space-3)]"
          style={{ background: 'var(--warning-soft)', color: 'var(--warning)', font: 'var(--t-small)' }}
        >
          <AlertTriangle size={16} /> No topics configured. Please configure topics first.
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Script Lab" description="Tune digest voice, tone, and pace per topic, then preview and save instructions." />

      <div className="card">
        {/* Message Display */}
        {message && (
          <div
            className="mb-[var(--space-4)] rounded-sm px-[var(--space-4)] py-[var(--space-3)]"
            style={{
              background: message.type === 'success' ? 'var(--success-soft)' : 'var(--danger-soft)',
              color: message.type === 'success' ? 'var(--success)' : 'var(--danger)',
              font: 'var(--t-small)',
            }}
          >
            {message.text}
          </div>
        )}

        {/* Controls */}
        <div className="mb-[var(--space-5)] grid grid-cols-1 items-end gap-[var(--space-3)] md:grid-cols-12">
          <div className="md:col-span-3">
            <label className="field-label">Topic</label>
            <select
              value={selectedTopic}
              onChange={(e) => setSelectedTopic(e.target.value)}
              className="select"
            >
              {topics.map((topic) => (
                <option key={topic.name} value={topic.name}>
                  {topic.name}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-3">
            <label className="field-label">Type of Show</label>
            <select
              value={scriptData.type_of_show}
              onChange={(e) => updateScriptData('type_of_show', e.target.value)}
              className="select"
            >
              {typeOfShowOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2">
            <label className="field-label">Voice</label>
            <select
              value={scriptData.voice_label}
              onChange={(e) => updateScriptData('voice_label', e.target.value)}
              className="select"
            >
              {voiceLabelOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2">
            <label className="field-label">Tone</label>
            <select
              value={scriptData.tone}
              onChange={(e) => updateScriptData('tone', e.target.value)}
              className="select"
            >
              {toneOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2">
            <label className="field-label">Pace</label>
            <select
              value={scriptData.pace}
              onChange={(e) => updateScriptData('pace', e.target.value)}
              className="select"
            >
              {paceOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-wrap gap-[var(--space-2)] md:col-span-12">
            <button
              onClick={() => handleAction('rewrite')}
              disabled={loading}
              className="btn btn-secondary"
            >
              {loading ? (
                <>
                  <Loader2 size={14} className="animate-spin" /> Processing…
                </>
              ) : (
                <>
                  <Sparkles size={14} /> Apply Knobs
                </>
              )}
            </button>
            <button
              onClick={() => handleAction('save')}
              disabled={loading}
              className="btn btn-secondary"
            >
              <Save size={14} /> Save Instructions
            </button>
            <button
              onClick={() => handleAction('preview')}
              disabled={loading}
              className="btn btn-secondary"
            >
              <Eye size={14} /> Generate Preview Script
            </button>
          </div>
        </div>

        {/* Content Areas */}
        <div className="grid grid-cols-1 gap-[var(--space-4)] md:grid-cols-2">
          <div>
            <label className="field-label">Digest Instructions (Markdown)</label>
            <textarea
              value={scriptData.content}
              onChange={(e) => updateScriptData('content', e.target.value)}
              rows={24}
              className="textarea min-h-[26rem] font-mono text-xs"
              placeholder="Enter digest instructions in Markdown format..."
            />
          </div>

          <div>
            <div className="mb-[var(--space-1)] flex items-center justify-between">
              <label className="field-label mb-0">Preview Script</label>
              {previewStats && (
                <div className="flex flex-wrap gap-x-[var(--space-3)] text-ink-subtle" style={{ font: 'var(--t-small)' }}>
                  {previewStats.mode && (
                    <span className="font-mono">
                      Mode: <span className="font-semibold text-ink-muted">{previewStats.mode}</span>
                    </span>
                  )}
                  {previewStats.episode_count !== undefined && (
                    <span className="font-mono">
                      Episodes: <span className="font-semibold text-ink-muted">{previewStats.episode_count}</span>
                    </span>
                  )}
                  {previewStats.char_count !== undefined && (
                    <span className="font-mono">
                      Chars: <span className="font-semibold text-ink-muted">{previewStats.char_count.toLocaleString()}</span>
                    </span>
                  )}
                  {previewStats.word_count !== undefined && (
                    <span className="font-mono">
                      Words: <span className="font-semibold text-ink-muted">{previewStats.word_count.toLocaleString()}</span>
                    </span>
                  )}
                </div>
              )}
            </div>
            <pre
              className="w-full overflow-auto rounded-sm border border-border bg-surface-2 p-[var(--space-3)] font-mono text-xs text-ink"
              style={{ minHeight: '26rem', whiteSpace: 'pre-wrap' }}
            >
              {preview || '—'}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
