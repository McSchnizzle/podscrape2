import { NextRequest, NextResponse } from "next/server";
import { DatabaseClient } from "@/utils/supabase";
import fs from "fs/promises";
import path from "path";

interface ScriptLabKnobs {
  type_of_show: string;
  voice_label: string;
  tone: string;
  pace: string;
}

// Project root is one level up from the hosted UI
const PROJECT_ROOT = path.join(process.cwd(), '..');

const editorKey = (topic: string, key: string): string => `${topic}:${key}`;

const loadTopicInstructions = async (topicName: string): Promise<string> => {
  try {
    const topicsPath = path.join(PROJECT_ROOT, 'config', 'topics.json');
    const topicsData = await fs.readFile(topicsPath, 'utf-8');
    const topicsConfig = JSON.parse(topicsData);

    const topic = topicsConfig.topics.find((t: any) => t.name === topicName);
    if (topic?.instruction_file) {
      const instructionPath = path.join(PROJECT_ROOT, 'digest_instructions', topic.instruction_file);
      try {
        return await fs.readFile(instructionPath, 'utf-8');
      } catch {
        return '';
      }
    }
    return '';
  } catch {
    return '';
  }
};

const saveTopicInstructions = async (topicName: string, content: string): Promise<void> => {
  try {
    const topicsPath = path.join(PROJECT_ROOT, 'config', 'topics.json');
    const topicsData = await fs.readFile(topicsPath, 'utf-8');
    const topicsConfig = JSON.parse(topicsData);

    const topic = topicsConfig.topics.find((t: any) => t.name === topicName);
    if (topic) {
      if (!topic.instruction_file) {
        topic.instruction_file = topicName.replace(/\s+/g, '_') + '.md';
      }

      const instructionPath = path.join(PROJECT_ROOT, 'digest_instructions', topic.instruction_file);
      await fs.writeFile(instructionPath, content, 'utf-8');

      // Save updated topics.json
      await fs.writeFile(topicsPath, JSON.stringify(topicsConfig, null, 2));
    }
  } catch (error) {
    throw new Error(`Failed to save instructions: ${error}`);
  }
};

const mapVoiceLabelToId = (label: string): string => {
  // Simplified voice mapping - in production you'd call VoiceManager
  const voiceMap: Record<string, string> = {
    'American news anchor': 'Qxm2h3F1LF2mSoFwF8Vp',
    'British man': 'VR6AewLTigWG4xSOukaG',
    'Black woman': 'EXAVITQu4vr4xnSDxMaL',
    'energetic millennial': 'pNInz6obpgDQGcFmaJgB'
  };
  return voiceMap[label] || voiceMap['American news anchor'];
};

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const topic = searchParams.get('topic');

    if (!topic) {
      return NextResponse.json({ error: 'Missing topic parameter' }, { status: 400 });
    }

    const db = new DatabaseClient();

    // Load topic instructions
    const content = await loadTopicInstructions(topic);

    // Load editor knobs from database settings (match Flask app format)
    const settings = await db.getSettings();
    const findSetting = (category: string, key: string): string | null => {
      const setting = settings.find(s => s.category === category && s.setting_key === key);
      return setting?.setting_value || null;
    };

    const typeOfShow = findSetting('editor', editorKey(topic, 'type_of_show')) || 'newscast';
    const voiceLabel = findSetting('editor', editorKey(topic, 'voice_label')) || 'American news anchor';
    const tone = findSetting('editor', editorKey(topic, 'tone')) || 'neutral';
    const pace = findSetting('editor', editorKey(topic, 'pace')) || 'moderate';

    return NextResponse.json({
      content,
      type_of_show: typeOfShow,
      voice_label: voiceLabel,
      tone,
      pace
    });
  } catch (error) {
    console.error('Script lab GET error:', error);
    return NextResponse.json({ error: 'Failed to load script lab data' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      action,
      topic,
      content,
      type_of_show,
      voice_label,
      tone,
      pace
    } = body;

    if (!topic) {
      return NextResponse.json({ error: 'Missing topic' }, { status: 400 });
    }

    const db = new DatabaseClient();

    if (action === 'save') {
      // Save instructions and knobs
      await saveTopicInstructions(topic, content);

      // Update voice_id in topics.json
      const voiceId = mapVoiceLabelToId(voice_label);
      const topicsPath = path.join(PROJECT_ROOT, 'config', 'topics.json');
      const topicsData = await fs.readFile(topicsPath, 'utf-8');
      const topicsConfig = JSON.parse(topicsData);

      const topicObj = topicsConfig.topics.find((t: any) => t.name === topic);
      if (topicObj) {
        topicObj.voice_id = voiceId;
        await fs.writeFile(topicsPath, JSON.stringify(topicsConfig, null, 2));
      }

      // Save editor knobs (match Flask app format)
      await db.updateSetting('editor', editorKey(topic, 'type_of_show'), type_of_show);
      await db.updateSetting('editor', editorKey(topic, 'voice_label'), voice_label);
      await db.updateSetting('editor', editorKey(topic, 'tone'), tone);
      await db.updateSetting('editor', editorKey(topic, 'pace'), pace);

      return NextResponse.json({
        success: true,
        message: 'Instructions and voice saved successfully'
      });
    }
    else if (action === 'rewrite') {
      // Call OpenAI to rewrite instructions based on knobs
      try {
        // This would require OpenAI integration - placeholder for now
        return NextResponse.json({
          success: true,
          content, // Return original for now
          message: 'Instructions rewrite not yet implemented'
        });
      } catch (error) {
        return NextResponse.json({ error: `OpenAI rewrite failed: ${error}` }, { status: 500 });
      }
    }
    else if (action === 'preview') {
      // Generate script preview - placeholder for now
      return NextResponse.json({
        success: true,
        preview: "Script preview generation not yet implemented - would show digest script using current instructions and scored episodes",
        message: 'Preview generated successfully'
      });
    }

    return NextResponse.json({ error: 'Invalid action' }, { status: 400 });
  } catch (error) {
    console.error('Script lab POST error:', error);
    return NextResponse.json({ error: 'Failed to process script lab request' }, { status: 500 });
  }
}