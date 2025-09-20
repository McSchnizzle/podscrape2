'use client';

import { useState, useEffect } from 'react';

interface Topic {
  name: string;
  instruction_file?: string;
  voice_id?: string;
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
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Load topics on mount
  useEffect(() => {
    const loadTopics = async () => {
      try {
        const response = await fetch('/api/topics');
        if (response.ok) {
          const data = await response.json();
          setTopics(data);
          if (data.length > 0 && !selectedTopic) {
            setSelectedTopic(data[0].name);
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
      <div className="container mx-auto px-4 py-8">
        <div className="bg-yellow-100 border border-yellow-400 text-yellow-700 px-4 py-3 rounded">
          No topics configured. Please configure topics first.
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="bg-white shadow rounded p-6">
        <h2 className="text-xl font-medium mb-4">Script Lab</h2>

        {/* Message Display */}
        {message && (
          <div className={`px-4 py-3 rounded mb-4 ${
            message.type === 'success'
              ? 'bg-green-100 border border-green-400 text-green-700'
              : 'bg-red-100 border border-red-400 text-red-700'
          }`}>
            {message.text}
          </div>
        )}

        {/* Controls */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end mb-4">
          <div className="md:col-span-3">
            <label className="block text-xs text-gray-600 mb-1">Topic</label>
            <select
              value={selectedTopic}
              onChange={(e) => setSelectedTopic(e.target.value)}
              className="border rounded w-full px-3 py-2"
            >
              {topics.map((topic) => (
                <option key={topic.name} value={topic.name}>
                  {topic.name}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-3">
            <label className="block text-xs text-gray-600 mb-1">Type of Show</label>
            <select
              value={scriptData.type_of_show}
              onChange={(e) => updateScriptData('type_of_show', e.target.value)}
              className="border rounded w-full px-3 py-2"
            >
              {typeOfShowOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-3">
            <label className="block text-xs text-gray-600 mb-1">Voice</label>
            <select
              value={scriptData.voice_label}
              onChange={(e) => updateScriptData('voice_label', e.target.value)}
              className="border rounded w-full px-3 py-2"
            >
              {voiceLabelOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-1">
            <label className="block text-xs text-gray-600 mb-1">Tone</label>
            <select
              value={scriptData.tone}
              onChange={(e) => updateScriptData('tone', e.target.value)}
              className="border rounded w-full px-3 py-2"
            >
              {toneOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-2">
            <label className="block text-xs text-gray-600 mb-1">Pace</label>
            <select
              value={scriptData.pace}
              onChange={(e) => updateScriptData('pace', e.target.value)}
              className="border rounded w-full px-3 py-2"
            >
              {paceOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-12 flex gap-2">
            <button
              onClick={() => handleAction('rewrite')}
              disabled={loading}
              className="px-3 py-2 rounded border bg-white hover:bg-gray-50 text-gray-800 border-gray-300 disabled:opacity-50"
            >
              {loading ? 'Processing...' : 'Apply Knobs'}
            </button>
            <button
              onClick={() => handleAction('save')}
              disabled={loading}
              className="px-3 py-2 rounded border bg-white hover:bg-gray-50 text-gray-800 border-gray-300 disabled:opacity-50"
            >
              Save Instructions
            </button>
            <button
              onClick={() => handleAction('preview')}
              disabled={loading}
              className="px-3 py-2 rounded border bg-white hover:bg-gray-50 text-gray-800 border-gray-300 disabled:opacity-50"
            >
              Generate Preview Script
            </button>
          </div>
        </div>

        {/* Content Areas */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              Digest Instructions (Markdown)
            </label>
            <textarea
              value={scriptData.content}
              onChange={(e) => updateScriptData('content', e.target.value)}
              rows={24}
              className="w-full border rounded p-2 font-mono text-xs"
              placeholder="Enter digest instructions in Markdown format..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Preview Script</label>
            <pre className="w-full border rounded p-2 bg-gray-50 text-xs overflow-auto"
                 style={{ minHeight: '26rem', whiteSpace: 'pre-wrap' }}>
              {preview || '—'}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}