import { useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { PageHeader } from '@/components/page-header';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { SourcesTab } from '../components/SourcesTab';
import { NodeSetsTab } from '../components/NodeSetsTab';
import { MappingsTab } from '../components/MappingsTab';
import { DataspaceTab } from '../components/DataspaceTab';

const TABS = ['sources', 'nodesets', 'mappings', 'dataspace'] as const;
type TabId = (typeof TABS)[number];

function resolveTab(hash: string): TabId {
  const cleaned = hash.replace('#', '') as TabId;
  return TABS.includes(cleaned) ? cleaned : 'sources';
}

export default function OPCUAPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeTab = resolveTab(location.hash);

  const handleTabChange = useCallback(
    (value: string) => {
      navigate({ hash: value }, { replace: true });
    },
    [navigate],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="OPC UA"
        description="Manage OPC UA server connections, information models, data mappings, and dataspace publication"
      />

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="sources">Sources</TabsTrigger>
          <TabsTrigger value="nodesets">NodeSets</TabsTrigger>
          <TabsTrigger value="mappings">Mappings</TabsTrigger>
          <TabsTrigger value="dataspace">Dataspace</TabsTrigger>
        </TabsList>

        <TabsContent value="sources">
          <SourcesTab />
        </TabsContent>

        <TabsContent value="nodesets">
          <NodeSetsTab />
        </TabsContent>

        <TabsContent value="mappings">
          <MappingsTab />
        </TabsContent>

        <TabsContent value="dataspace">
          <DataspaceTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
