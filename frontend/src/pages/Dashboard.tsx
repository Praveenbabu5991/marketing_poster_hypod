import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStore } from '../store/useStore';
import { listAgents } from '../api/agents';
import { getBrand } from '../api/brands';
import { createSession } from '../api/sessions';
import { AgentCard } from '../components/AgentCard';
import type { Agent, Brand } from '../types';

export function Dashboard() {
  const { selectedBrandId } = useStore();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selectedBrand, setSelectedBrand] = useState<Brand | null>(null);
  const [creating, setCreating] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    listAgents().then(setAgents).catch(console.error);
  }, []);

  // Get brand details from sidebar brands (passed via outlet context isn't great, so we fetch)
  useEffect(() => {
    if (!selectedBrandId) {
      setSelectedBrand(null);
      return;
    }
    getBrand(selectedBrandId).then(setSelectedBrand).catch(() => setSelectedBrand(null));
  }, [selectedBrandId]);

  async function handleAgentClick(agent: Agent) {
    if (!selectedBrandId || creating) return;

    setCreating(agent.id);
    try {
      const session = await createSession({
        brand_id: selectedBrandId,
        agent_type: agent.id,
      });
      navigate(`/chat/${session.id}`);
    } catch (err) {
      console.error('Failed to create session:', err);
    } finally {
      setCreating(null);
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <h1 className="mb-2 text-2xl font-bold text-text-primary">Dashboard</h1>
      <p className="mb-8 text-text-muted">
        {selectedBrandId
          ? `Create content for ${selectedBrand?.name || 'your brand'}`
          : 'Select a brand from the sidebar to get started'}
      </p>

      {/* Agent Grid */}
      <h2 className="mb-4 text-lg font-semibold text-text-primary">Agents</h2>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {agents.map((agent) => (
          <AgentCard
            key={agent.id}
            agent={agent}
            disabled={!selectedBrandId || creating === agent.id}
            onClick={() => handleAgentClick(agent)}
          />
        ))}
      </div>

      {creating && (
        <p className="mt-4 text-sm text-text-muted">Creating session...</p>
      )}
    </div>
  );
}
