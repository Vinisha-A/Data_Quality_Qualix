import json
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from mappings.models import Mapping, PipelineGroup, PipelineGroupAssignment
from connections.models import DataConnection

class PipelineGroupingTestCase(TestCase):
    def setUp(self):
        # Create a test user and log in
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.login(username='testuser', password='password123')

        # Create dummy connections
        self.conn1 = DataConnection.objects.create(
            name='Source Connection',
            connection_type='postgresql',
            host='localhost',
            database_name='src_db',
            created_by=self.user
        )
        self.conn2 = DataConnection.objects.create(
            name='Target Connection',
            connection_type='postgresql',
            host='localhost',
            database_name='tgt_db',
            created_by=self.user
        )

        try:
            from accounts.models import UserProfile
            self.profile, _ = UserProfile.objects.get_or_create(user=self.user, defaults={'role': 'admin'})
            self.profile.role = 'admin'
            self.profile.save()
        except ImportError:
            pass

    def test_naming_convention_submenu_filtering(self):
        """Verify that mapping names match their naming conventions and filter correctly via GET params."""
        m1 = Mapping.objects.create(name='LH_to_MKT_UC_sales', source_connection=self.conn1, target_connection=self.conn2, created_by=self.user)
        m2 = Mapping.objects.create(name='MKT_ORA_TO_MKT_UC_orders', source_connection=self.conn1, target_connection=self.conn2, created_by=self.user)
        m3 = Mapping.objects.create(name='MKT_CLOUD_PG_TO_MKT_UC_logs', source_connection=self.conn1, target_connection=self.conn2, created_by=self.user)
        m4 = Mapping.objects.create(name='EDW_TO_LH_records', source_connection=self.conn1, target_connection=self.conn2, created_by=self.user)
        m5 = Mapping.objects.create(name='Custom_Pipeline', source_connection=self.conn1, target_connection=self.conn2, created_by=self.user)

        # 1. Test All Pipelines group (default list view)
        response = self.client.get(reverse('mappings:list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['mappings']), 5)

        # 2. Filter by LH_to_MKT_UC group
        response = self.client.get(reverse('mappings:list') + '?group=lh_to_mkt_uc')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['mappings']), 1)
        self.assertEqual(response.context['mappings'][0], m1)

        # 3. Filter by MKT_ORA_TO_MKT_UC group
        response = self.client.get(reverse('mappings:list') + '?group=mkt_ora_to_mkt_uc')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['mappings']), 1)
        self.assertEqual(response.context['mappings'][0], m2)

        # 4. Filter by MKT_CLOUD_PG_TO_MKT_UC group
        response = self.client.get(reverse('mappings:list') + '?group=mkt_cloud_pg_to_mkt_uc')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['mappings']), 1)
        self.assertEqual(response.context['mappings'][0], m3)

        # 5. Filter by EDW_TO_LH group
        response = self.client.get(reverse('mappings:list') + '?group=edw_to_lh')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['mappings']), 1)
        self.assertEqual(response.context['mappings'][0], m4)

        # 6. Filter by Other Pipelines group
        response = self.client.get(reverse('mappings:list') + '?group=other')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['mappings']), 1)
        self.assertEqual(response.context['mappings'][0], m5)

    def test_create_pipeline_group(self):
        """Test API endpoint to create a pipeline group."""
        url = reverse('mappings:create_group')
        
        # Valid group creation
        response = self.client.post(url, {'name': 'Operations'})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['group']['name'], 'Operations')
        
        # Duplicate group creation
        response = self.client.post(url, {'name': 'operations'})
        self.assertEqual(response.status_code, 400)
        
        # Reserved name group creation
        response = self.client.post(url, {'name': 'EDW_TO_LH'})
        self.assertEqual(response.status_code, 400)

    def test_assign_group_pipelines(self):
        """Test assigning mappings to custom groups."""
        group = PipelineGroup.objects.create(name='Sales')
        m1 = Mapping.objects.create(name='LH_to_MKT_UC_sales', source_connection=self.conn1, target_connection=self.conn2, created_by=self.user)
        m2 = Mapping.objects.create(name='Custom_Pipeline', source_connection=self.conn1, target_connection=self.conn2, created_by=self.user)
        
        url = reverse('mappings:assign_group_pipelines', args=[group.id])
        
        # Assign mappings to group
        payload = json.dumps({'mapping_ids': [m1.id, m2.id]})
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        # Verify filtering of display_mappings by custom group
        response = self.client.get(reverse('mappings:list') + f'?group=custom_{group.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['mappings']), 2)
        
        # Reassigned m1 should not appear in its default convention group now
        response = self.client.get(reverse('mappings:list') + '?group=lh_to_mkt_uc')
        self.assertEqual(len(response.context['mappings']), 0)

    def test_delete_pipeline_group(self):
        """Test custom group deletion Cascades assignments cleanly."""
        group = PipelineGroup.objects.create(name='Marketing')
        m1 = Mapping.objects.create(name='LH_to_MKT_UC_sales', source_connection=self.conn1, target_connection=self.conn2, created_by=self.user)
        PipelineGroupAssignment.objects.create(group=group, mapping=m1)
        
        url = reverse('mappings:delete_group', args=[group.id])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        
        # Verify mapping falls back to its default convention group
        response = self.client.get(reverse('mappings:list') + '?group=lh_to_mkt_uc')
        self.assertEqual(len(response.context['mappings']), 1)
        self.assertEqual(response.context['mappings'][0], m1)

    def test_create_pipeline_inside_group(self):
        """Test that creating a new pipeline via POST with a group parameter maps it to that custom group."""
        group = PipelineGroup.objects.create(name='Finance')
        
        create_url = reverse('mappings:create')
        data = {
            'name': 'New Finance Pipeline',
            'source_connection': self.conn1.id,
            'target_connection': self.conn2.id,
            'source_table': 'src_tbl',
            'target_table': 'tgt_tbl',
            'group': f'custom_{group.id}',
        }
        
        response = self.client.post(create_url, data)
        self.assertEqual(response.status_code, 302)
        
        # Verify the new mapping exists and is assigned to the group
        mapping = Mapping.objects.get(name='New Finance Pipeline')
        assignment = PipelineGroupAssignment.objects.filter(mapping=mapping).first()
        self.assertIsNotNone(assignment)
        self.assertEqual(assignment.group, group)
