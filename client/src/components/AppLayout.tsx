import React from 'react';
import { Layout, Typography, Menu } from 'antd';
import { DashboardOutlined, BarChartOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';

const { Sider, Content } = Layout;

const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider width={180} theme="light" style={{ borderRight: '1px solid #f0f0f0' }}>
        <div style={{ height: 56, display: 'flex', alignItems: 'center', justifyContent: 'center', borderBottom: '1px solid #f0f0f0' }}>
          <Typography.Text strong style={{ fontSize: 16 }}>BSMS Tracking</Typography.Text>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[location.pathname]}
          items={[
            { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
            { key: '/gantt', icon: <BarChartOutlined />, label: '甘特图' },
            { key: '/timeline', icon: <ClockCircleOutlined />, label: '时间节点' },
          ]}
          onClick={({ key }) => navigate(key)}
          style={{ border: 'none' }}
        />
      </Sider>
      <Layout>
        <Content style={{ padding: 24, background: '#f5f5f5', overflow: 'auto', maxHeight: '100vh' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
