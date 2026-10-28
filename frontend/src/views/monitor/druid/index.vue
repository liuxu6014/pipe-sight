<template>
   <div class="app-container">
      <el-result icon="info" title="数据监控暂不可用" sub-title="当前页面尚未接入数据监控服务，无法展示监控指标。如需启用，请联系管理员核实可用的监控能力与访问配置。">
         <template #extra>
            <router-link to="/portal"><el-button type="primary">返回门户</el-button></router-link>
         </template>
      </el-result>
   </div>
</template>
