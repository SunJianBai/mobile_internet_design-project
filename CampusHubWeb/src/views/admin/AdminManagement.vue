<template>
  <div class="admin-page">
    <el-card class="admin-panel" shadow="never">
      <template #header>
        <div class="panel-title">
          <div>
            <span>{{ pageConfig.title }}</span>
            <p>{{ pageConfig.description }}</p>
          </div>
          <div class="panel-actions">
            <el-input
              v-model="keyword"
              class="table-search"
              clearable
              placeholder="搜索关键词"
              @keyup.enter="handleKeywordSearch"
              @clear="handleKeywordSearch"
            />
            <el-button type="primary" @click="loadData">刷新</el-button>
          </div>
        </div>
      </template>

      <template v-if="mode === 'users'">
        <div class="toolbar-row">
          <el-select v-model="userTypeFilter" clearable placeholder="按角色筛选" @change="handleFilterChange">
            <el-option v-for="item in userTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select v-model="userStatusFilter" clearable placeholder="按状态筛选" @change="handleFilterChange">
            <el-option v-for="item in userStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </div>
        <el-table :data="filteredRows" v-loading="loading" :class="adminTableClass" :size="tableSize">
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column label="用户" min-width="220">
            <template #default="{ row }">
              <div class="table-user">
                <span class="table-avatar">{{ (row.nickname || row.email || '用').slice(0, 1) }}</span>
                <div>
                  <strong>{{ row.nickname || '未设置昵称' }}</strong>
                  <p>{{ row.email }}</p>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="注册时间" min-width="160">
            <template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template>
          </el-table-column>
          <el-table-column label="角色" width="160">
            <template #default="{ row }">
              <el-tooltip
                content="不能修改自己的管理员权限"
                placement="top"
                :disabled="!isCurrentAdminUser(row)"
              >
                <span class="guarded-control">
                  <el-select
                    v-model="row.userType"
                    size="small"
                    :disabled="isCurrentAdminUser(row)"
                    @change="(value) => updateUserRole(row, value)"
                  >
                    <el-option label="普通用户" value="COMMON" />
                    <el-option label="管理员" value="ADMIN" />
                  </el-select>
                </span>
              </el-tooltip>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-select
                v-model="row.userStatus"
                size="small"
                :class="['status-select', statusTone(row.userStatus)]"
                @change="(value) => updateUserStatus(row, value)"
              >
                <el-option
                  v-for="item in userStatusOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                  :disabled="isSelfBanOption(row, item.value)"
                />
              </el-select>
            </template>
          </el-table-column>
        </el-table>

      </template>

      <template v-else-if="mode === 'orders'">
        <div class="toolbar-row">
          <el-select v-model="orderStatus" clearable placeholder="按状态筛选" @change="loadData">
            <el-option v-for="item in orderStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select v-model="orderActivityType" clearable placeholder="按活动类型筛选" @change="loadData">
            <el-option v-for="item in activityTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
          <el-select v-model="orderCampus" clearable placeholder="按校区筛选" @change="loadData">
            <el-option v-for="item in campusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </div>
        <el-table :data="filteredRows" v-loading="loading" :class="adminTableClass" :size="tableSize">
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column label="活动" min-width="220">
            <template #default="{ row }">
              <strong>{{ activityLabel(row.activityType) }}</strong>
              <p class="muted-line">{{ row.location }} / {{ campusLabel(row.campus) }}</p>
            </template>
          </el-table-column>
          <el-table-column label="发布者" min-width="150">
            <template #default="{ row }">{{ row.user?.nickname || '未知用户' }}</template>
          </el-table-column>
          <el-table-column label="人数" width="100">
            <template #default="{ row }">{{ row.currentPeople }}/{{ row.maxPeople }}</template>
          </el-table-column>
          <el-table-column label="开始时间" min-width="160">
            <template #default="{ row }">{{ formatDateTime(row.startTime) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="160">
            <template #default="{ row }">
              <el-select v-model="row.status" size="small" @change="(value) => updateOrder(row, value)">
                <el-option v-for="item in orderStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </template>
          </el-table-column>
        </el-table>

      </template>

      <template v-else-if="mode === 'contents' || mode === 'comments'">
        <div class="toolbar-row">
          <el-select v-model="contentStatus" clearable placeholder="按内容状态筛选" @change="loadData">
            <el-option v-for="item in contentStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </div>
        <el-table :data="filteredRows" v-loading="loading" :class="adminTableClass" :size="tableSize">
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column label="内容" min-width="360">
            <template #default="{ row }">
              <strong class="content-snippet">{{ row.content }}</strong>
              <p class="muted-line">{{ row.user?.nickname || row.user?.email || '未知用户' }} / {{ formatDateTime(row.createdAt) }}</p>
              <p v-if="row.parent" class="muted-line">回复：{{ row.parent.content }}</p>
              <p v-else-if="row.order" class="muted-line">关联活动：{{ activityLabel(row.order.activityType) }} / {{ row.order.location }}</p>
            </template>
          </el-table-column>
          <el-table-column label="互动" width="150">
            <template #default="{ row }">
              <span>{{ row.likeCount || 0 }} 赞 / {{ row.commentCount || 0 }} 评</span>
            </template>
          </el-table-column>
          <el-table-column label="媒体" width="110">
            <template #default="{ row }">
              <el-tag effect="plain">{{ row.mediaType || 'TEXT' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="140">
            <template #default="{ row }">
              <el-select
                v-model="row.status"
                size="small"
                :class="['status-select', contentStatusTone(row.status)]"
                @change="(value) => updateContent(row, value)"
              >
                <el-option v-for="item in contentStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'DELETED'"
                type="success"
                size="small"
                plain
                @click="restoreContent(row)"
              >
                恢复
              </el-button>
              <el-button v-else type="danger" size="small" plain @click="removeContent(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-else-if="mode === 'ai'">
        <el-table :data="filteredRows" v-loading="loading" :class="adminTableClass" :size="tableSize">
          <el-table-column prop="category" label="类型" width="110" />
          <el-table-column label="内容" min-width="320">
            <template #default="{ row }">
              <strong>{{ row.title || row.content || row.summary || `会话 #${row.id || row.cid}` }}</strong>
              <p class="muted-line">{{ formatDateTime(row.updatedAt || row.createdAt) }}</p>
            </template>
          </el-table-column>
          <el-table-column label="用户" min-width="180">
            <template #default="{ row }">
              <div class="table-user">
                <span class="table-avatar">{{ (row.user?.nickname || row.user?.email || '用').slice(0, 1) }}</span>
                <div>
                  <strong>{{ row.user?.nickname || '未知用户' }}</strong>
                  <p>{{ row.user?.email || '-' }}</p>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="说明">
            <template #default="{ row }">
              <span v-if="row.category === '记忆'">长期记忆 / {{ row.memoryCategory || row.source || '未分类' }}</span>
              <span v-else>会话消息 {{ row.messageCount || 0 }} 条</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <div class="ai-table-actions">
                <el-button
                  v-if="!isAiMemory(row)"
                  size="small"
                  plain
                  @click="openAiConversation(row)"
                >
                  查看
                </el-button>
                <el-button type="danger" size="small" plain @click="removeAiRecord(row)">删除</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-else-if="mode === 'files'">
        <div class="toolbar-row">
          <el-select v-model="fileType" clearable placeholder="按类型筛选" @change="loadData">
            <el-option v-for="item in fileTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </div>
        <el-table :data="filteredRows" v-loading="loading" :class="adminTableClass" :size="tableSize">
          <el-table-column prop="pmid" label="ID" width="90" />
          <el-table-column label="资源" min-width="280">
            <template #default="{ row }">
              <div class="file-resource">
                <div class="file-thumb" :class="{ video: row.mediaType === 'VIDEO' }">
                  <img v-if="row.mediaType === 'IMAGE'" :src="resolveFileUrl(row.url)" :alt="row.filename" />
                  <span v-else>VIDEO</span>
                </div>
                <div>
                  <strong>{{ row.filename || row.url }}</strong>
                  <p class="muted-line">{{ row.url }}</p>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="110">
            <template #default="{ row }">
              <el-tag effect="plain">{{ fileTypeLabel(row.mediaType) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="来源内容" min-width="240">
            <template #default="{ row }">
              <strong class="content-snippet">{{ row.postContent || '未关联内容' }}</strong>
              <p class="muted-line">{{ row.user?.nickname || row.user?.email || '未知用户' }}</p>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="110">
            <template #default="{ row }">{{ formatFileSize(row.size) }}</template>
          </el-table-column>
          <el-table-column label="上传时间" min-width="160">
            <template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <el-button type="danger" size="small" plain @click="removeFile(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-else-if="mode === 'logs'">
        <div class="toolbar-row">
          <el-select v-model="auditModule" clearable placeholder="按模块筛选" @change="loadData">
            <el-option v-for="item in auditModuleOptions" :key="item" :label="item" :value="item" />
          </el-select>
          <el-select v-model="auditAction" clearable placeholder="按动作筛选" @change="loadData">
            <el-option
              v-for="item in auditActionOptions"
              :key="item.value"
              :label="item.label"
              :value="item.value"
            />
          </el-select>
        </div>
        <el-table :data="filteredRows" v-loading="loading" :class="adminTableClass" :size="tableSize">
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column label="模块" width="120">
            <template #default="{ row }">
              <el-tag effect="plain">{{ row.moduleName || '-' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="动作" width="130">
            <template #default="{ row }">{{ row.actionLabel || auditActionLabel(row.action) }}</template>
          </el-table-column>
          <el-table-column label="目标" width="150">
            <template #default="{ row }">
              <strong>{{ row.targetType || '-' }}</strong>
              <p class="muted-line">{{ auditTargetLabel(row) }}</p>
            </template>
          </el-table-column>
          <el-table-column label="详情" min-width="360">
            <template #default="{ row }">
              <strong class="content-snippet">{{ row.detail || '-' }}</strong>
            </template>
          </el-table-column>
          <el-table-column label="操作者" min-width="180">
            <template #default="{ row }">
              <div class="table-user">
                <span class="table-avatar">{{ (row.operator?.nickname || row.operator?.email || '管').slice(0, 1) }}</span>
                <div>
                  <strong>{{ row.operator?.nickname || '未知管理员' }}</strong>
                  <p>{{ row.operator?.email || '-' }}</p>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="IP" width="140">
            <template #default="{ row }">{{ row.ipAddress || '-' }}</template>
          </el-table-column>
          <el-table-column label="时间" min-width="170">
            <template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template>
          </el-table-column>
        </el-table>
      </template>

      <template v-else-if="mode === 'settings'">
        <div class="settings-grid">
          <el-card shadow="never" class="settings-card">
            <template #header>后台偏好</template>
            <el-form label-width="120px">
              <el-form-item label="紧凑表格">
                <el-switch v-model="settings.compactTable" />
              </el-form-item>
              <el-form-item label="操作确认">
                <el-switch v-model="settings.confirmActions" />
              </el-form-item>
              <el-form-item label="默认分页">
                <el-input-number v-model="settings.pageSize" :min="10" :max="50" :step="10" />
              </el-form-item>
            </el-form>
          </el-card>
          <el-card shadow="never" class="settings-card">
            <template #header>运维策略</template>
            <el-form label-width="120px">
              <el-form-item label="内容巡检">
                <el-switch v-model="settings.contentAuditEnabled" />
              </el-form-item>
              <el-form-item label="开放注册">
                <el-switch v-model="settings.allowPublicRegistration" />
              </el-form-item>
              <el-form-item label="上传上限">
                <el-input-number v-model="settings.maxUploadSizeMb" :min="1" :max="20" />
                <span class="setting-unit">MB</span>
              </el-form-item>
              <el-form-item label="维护公告">
                <el-input
                  v-model="settings.maintenanceNotice"
                  type="textarea"
                  :rows="3"
                  maxlength="120"
                  show-word-limit
                  placeholder="留空则不展示维护公告"
                />
              </el-form-item>
            </el-form>
          </el-card>
        </div>
        <div class="settings-actions">
          <el-button type="primary" :loading="loading" @click="saveSettings">保存设置</el-button>
        </div>
      </template>

      <template v-else>
        <el-empty :description="pageConfig.empty" />
      </template>

      <div v-if="showMobileCards" class="admin-mobile-cards">
        <article
          v-for="row in filteredRows"
          :key="mobileRowKey(row)"
          :class="['admin-mobile-card', { 'content-mobile-card': mode === 'contents' || mode === 'comments' || mode === 'logs' }]"
        >
          <div class="admin-mobile-card-head">
            <div class="admin-mobile-identity">
              <span class="table-avatar">{{ mobileInitial(row) }}</span>
              <div>
                <strong>{{ mobileTitle(row) }}</strong>
                <p>{{ mobileSubtitle(row) }}</p>
              </div>
            </div>
            <el-tag effect="light">{{ mobileBadge(row) }}</el-tag>
          </div>

          <div class="admin-mobile-meta">
            <div v-for="item in mobileMeta(row)" :key="item.label">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>

          <div v-if="mode === 'users'" class="admin-mobile-actions">
            <el-tooltip
              content="不能修改自己的管理员权限"
              placement="top"
              :disabled="!isCurrentAdminUser(row)"
            >
              <span class="guarded-control">
                <el-select
                  v-model="row.userType"
                  size="small"
                  :disabled="isCurrentAdminUser(row)"
                  @change="(value) => updateUserRole(row, value)"
                >
                  <el-option label="普通用户" value="COMMON" />
                  <el-option label="管理员" value="ADMIN" />
                </el-select>
              </span>
            </el-tooltip>
            <el-select
              v-model="row.userStatus"
              size="small"
              :class="['status-select', statusTone(row.userStatus)]"
              @change="(value) => updateUserStatus(row, value)"
            >
              <el-option
                v-for="item in userStatusOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
                :disabled="isSelfBanOption(row, item.value)"
              />
            </el-select>
          </div>

          <div v-else-if="mode === 'orders'" class="admin-mobile-actions">
            <el-select v-model="row.status" size="small" @change="(value) => updateOrder(row, value)">
              <el-option v-for="item in orderStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </div>

          <div v-else-if="mode === 'contents' || mode === 'comments'" class="admin-mobile-actions">
            <el-select
              v-model="row.status"
              size="small"
              :class="['status-select', contentStatusTone(row.status)]"
              @change="(value) => updateContent(row, value)"
            >
              <el-option v-for="item in contentStatusOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
            <el-button
              v-if="row.status === 'DELETED'"
              type="success"
              size="small"
              plain
              @click="restoreContent(row)"
            >
              恢复内容
            </el-button>
            <el-button v-else type="danger" size="small" plain @click="removeContent(row)">删除内容</el-button>
          </div>

          <div v-else-if="mode === 'ai'" class="admin-mobile-actions">
            <el-button v-if="!isAiMemory(row)" size="small" plain @click="openAiConversation(row)">
              查看会话
            </el-button>
            <el-button type="danger" size="small" plain @click="removeAiRecord(row)">删除记录</el-button>
          </div>

          <div v-else-if="mode === 'files'" class="admin-mobile-actions">
            <el-button type="danger" size="small" plain @click="removeFile(row)">删除资源</el-button>
          </div>
        </article>
      </div>

      <el-empty v-if="showMobileEmpty" class="admin-mobile-empty" :description="pageConfig.empty" />

      <div v-if="hasPagination" class="admin-pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          background
          layout="total, sizes, prev, pager, next"
          :total="pagination.total"
          :page-sizes="paginationSizes"
          @size-change="handlePageSizeChange"
          @current-change="loadData"
        />
      </div>

      <section v-if="mode === 'orders'" class="order-audit-section">
        <div class="audit-section-head">
          <div>
            <strong>报名申请审核</strong>
            <p>集中处理活动报名，通过后会同步更新订单人数。</p>
          </div>
          <div class="audit-section-tools">
            <el-select v-model="applicationStatus" clearable placeholder="申请状态" @change="loadApplications">
              <el-option
                v-for="item in applicationStatusOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
            </el-select>
            <el-button :loading="applicationLoading" @click="loadApplications">刷新申请</el-button>
          </div>
        </div>

        <el-table
          :data="applicationRows"
          v-loading="applicationLoading"
          :class="adminTableClass"
          :size="tableSize"
          empty-text="暂无申请记录"
        >
          <el-table-column prop="id" label="申请ID" width="100" />
          <el-table-column label="申请人" min-width="190">
            <template #default="{ row }">
              <div class="table-user">
                <span class="table-avatar">{{ (row.user?.nickname || row.user?.email || '申').slice(0, 1) }}</span>
                <div>
                  <strong>{{ row.user?.nickname || '未知用户' }}</strong>
                  <p>{{ row.user?.email || '-' }}</p>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="活动" min-width="230">
            <template #default="{ row }">
              <strong>{{ activityLabel(row.order?.activityType) }}</strong>
              <p class="muted-line">{{ row.order?.location || '-' }} / {{ campusLabel(row.order?.campus) }}</p>
            </template>
          </el-table-column>
          <el-table-column label="发布者" min-width="150">
            <template #default="{ row }">{{ row.order?.user?.nickname || row.order?.user?.email || '未知用户' }}</template>
          </el-table-column>
          <el-table-column label="人数" width="100">
            <template #default="{ row }">{{ row.order?.currentPeople || 0 }}/{{ row.order?.maxPeople || 0 }}</template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="applicationTone(row.status)" effect="plain">
                {{ applicationStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button
                type="success"
                size="small"
                plain
                :disabled="row.status === 'APPROVED' || row.status === 'CANCELLED_APPLY'"
                @click="auditApplication(row, 'APPROVED')"
              >
                通过
              </el-button>
              <el-button
                type="danger"
                size="small"
                plain
                :disabled="row.status === 'REJECTED' || row.status === 'CANCELLED_APPLY'"
                @click="auditApplication(row, 'REJECTED')"
              >
                驳回
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="applicationRows.length" class="application-mobile-cards">
          <article v-for="row in applicationRows" :key="row.id" class="application-card">
            <div class="application-card-head">
              <div>
                <strong>{{ activityLabel(row.order?.activityType) }} · {{ row.order?.location || '-' }}</strong>
                <p>{{ row.user?.nickname || row.user?.email || '未知用户' }} 申请加入</p>
              </div>
              <el-tag :type="applicationTone(row.status)" effect="plain">
                {{ applicationStatusLabel(row.status) }}
              </el-tag>
            </div>
            <div class="application-card-meta">
              <span>{{ campusLabel(row.order?.campus) }}</span>
              <span>{{ row.order?.currentPeople || 0 }}/{{ row.order?.maxPeople || 0 }} 人</span>
              <span>{{ formatDateTime(row.createdAt) }}</span>
            </div>
            <div class="admin-mobile-actions">
              <el-button
                type="success"
                plain
                :disabled="row.status === 'APPROVED' || row.status === 'CANCELLED_APPLY'"
                @click="auditApplication(row, 'APPROVED')"
              >
                通过
              </el-button>
              <el-button
                type="danger"
                plain
                :disabled="row.status === 'REJECTED' || row.status === 'CANCELLED_APPLY'"
                @click="auditApplication(row, 'REJECTED')"
              >
                驳回
              </el-button>
            </div>
          </article>
        </div>
        <el-empty
          v-else-if="!applicationLoading"
          class="application-mobile-empty"
          description="暂无申请记录"
        />
      </section>
    </el-card>

    <el-drawer
      v-model="aiDrawerVisible"
      class="ai-audit-drawer"
      :title="aiDetail.conversation?.title || 'AI会话详情'"
      size="520px"
      append-to-body
    >
      <div v-loading="aiDetailLoading" class="ai-detail">
        <div v-if="aiDetail.conversation" class="ai-detail-summary">
          <div>
            <span>用户</span>
            <strong>
              {{ aiDetail.conversation.user?.nickname || aiDetail.conversation.user?.email || '未知用户' }}
            </strong>
          </div>
          <div>
            <span>消息</span>
            <strong>{{ aiDetail.conversation.messageCount || aiDetail.messages.length || 0 }} 条</strong>
          </div>
          <div>
            <span>更新时间</span>
            <strong>{{ formatDateTime(aiDetail.conversation.updatedAt) }}</strong>
          </div>
        </div>

        <div v-if="aiDetail.messages.length" class="ai-message-list">
          <article
            v-for="message in aiDetail.messages"
            :key="message.mid || message.id"
            :class="['ai-message-card', message.role || 'assistant']"
          >
            <div class="ai-message-head">
              <strong>{{ aiRoleLabel(message.role) }}</strong>
              <span>{{ formatDateTime(message.createdAt) }}</span>
            </div>
            <p>{{ message.content }}</p>
            <div v-if="message.toolName || message.tokenCount" class="ai-message-meta">
              <span v-if="message.toolName">工具：{{ message.toolName }}</span>
              <span v-if="message.tokenCount">Token：{{ message.tokenCount }}</span>
            </div>
          </article>
        </div>
        <el-empty v-else-if="!aiDetailLoading" description="暂无会话消息" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  auditAdminOrderApplication,
  deleteAdminAiConversation,
  deleteAdminAiMemory,
  deleteAdminFile,
  deleteAdminContent,
  getAdminAuditLogs,
  getAdminAiConversationMessages,
  getAdminAiAuditItems,
  getAdminContents,
  getAdminFiles,
  getAdminOrderApplications,
  getAdminOrders,
  getAdminSettings,
  getAdminUsers,
  updateAdminContentStatus,
  updateAdminSettings,
  updateAdminOrderStatus,
  updateAdminUserStatus,
  updateAdminUserType
} from '../../services/admin'

const route = useRoute()
const loading = ref(false)
const applicationLoading = ref(false)
const aiDetailLoading = ref(false)
const rows = ref([])
const applicationRows = ref([])
const keyword = ref(typeof route.query.q === 'string' ? route.query.q : '')
const userTypeFilter = ref('')
const userStatusFilter = ref('')
const orderStatus = ref('')
const orderActivityType = ref('')
const orderCampus = ref('')
const applicationStatus = ref('')
const contentStatus = ref('')
const fileType = ref('')
const auditModule = ref('')
const auditAction = ref('')
const settingsLoaded = ref(false)
const settings = reactive({
  compactTable: true,
  confirmActions: true,
  pageSize: 20,
  contentAuditEnabled: true,
  allowPublicRegistration: true,
  maxUploadSizeMb: 20,
  maintenanceNotice: ''
})
const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
})
const aiDetail = reactive({
  conversation: null,
  messages: []
})
const aiDrawerVisible = ref(false)
const currentAdminUserId = computed(() => Number(localStorage.getItem('userId') || 0))

const mode = computed(() => route.meta.adminMode || 'placeholder')

const pageConfigs = {
  users: {
    title: '用户管理',
    description: '查看用户资料、维护管理员权限与账号状态。',
    empty: '暂无用户数据'
  },
  orders: {
    title: '活动订单',
    description: '巡检活动预约，按状态筛选并调整订单生命周期。',
    empty: '暂无活动订单'
  },
  contents: {
    title: '动态内容',
    description: '管理用户发布的校园动态，支持快速删除违规内容。',
    empty: '暂无动态内容'
  },
  comments: {
    title: '评论审核',
    description: '集中查看评论回复，处理不合规互动。',
    empty: '暂无评论'
  },
  ai: {
    title: 'AI会话',
    description: '审计全量 AI 会话与长期记忆状态。',
    empty: '暂无 AI 会话或记忆'
  },
  files: {
    title: '文件资源',
    description: '浏览上传图片与视频，清理无效或违规资源。',
    empty: '暂无文件资源'
  },
  logs: {
    title: '操作日志',
    description: '追踪后台关键操作、操作者、目标对象与来源 IP。',
    empty: '暂无操作日志'
  },
  settings: {
    title: '系统设置',
    description: '配置后台偏好、内容巡检与运维策略。',
    empty: '暂无系统设置'
  }
}

const pageConfig = computed(() => pageConfigs[mode.value] || pageConfigs.settings)
const hasPagination = computed(() => ['users', 'orders', 'contents', 'comments', 'files', 'ai', 'logs'].includes(mode.value))
const serverKeywordModes = ['users', 'orders', 'contents', 'comments', 'files', 'ai', 'logs']
const tableSize = computed(() => (settings.compactTable ? 'small' : 'default'))
const adminTableClass = computed(() => ({
  'admin-table': true,
  'admin-table-compact': settings.compactTable
}))
const paginationSizes = computed(() => {
  const preferred = Number(settings.pageSize || 20)
  return Array.from(new Set([10, 20, 30, 40, 50, preferred]))
    .filter((value) => value >= 10 && value <= 50)
    .sort((a, b) => a - b)
})

const orderStatusOptions = [
  { label: '待匹配', value: 'PENDING' },
  { label: '进行中', value: 'IN_PROGRESS' },
  { label: '已完成', value: 'COMPLETED' },
  { label: '已取消', value: 'CANCELLED' },
  { label: '已过期', value: 'EXPIRED' }
]

const applicationStatusOptions = [
  { label: '待审核', value: 'PENDING_REVIEW' },
  { label: '已通过', value: 'APPROVED' },
  { label: '已驳回', value: 'REJECTED' },
  { label: '已撤销', value: 'CANCELLED_APPLY' }
]

const contentStatusOptions = [
  { label: '正常', value: 'NORMAL' },
  { label: '待审', value: 'PENDING' },
  { label: '驳回', value: 'REJECTED' },
  { label: '已删除', value: 'DELETED' }
]

const userStatusOptions = [
  { label: '在线', value: 'ONLINE' },
  { label: '离线', value: 'OFFLINE' },
  { label: '封禁', value: 'BANNED' }
]

const userTypeOptions = [
  { label: '普通用户', value: 'COMMON' },
  { label: '管理员', value: 'ADMIN' }
]

const fileTypeOptions = [
  { label: '图片', value: 'IMAGE' },
  { label: '视频', value: 'VIDEO' }
]

const auditModuleOptions = ['用户管理', '活动订单', '动态内容', '评论审核', '文件资源', 'AI会话', '系统设置']

const auditActionOptions = [
  { label: '修改角色', value: 'USER_TYPE_UPDATE' },
  { label: '修改状态', value: 'USER_STATUS_UPDATE' },
  { label: '订单调度', value: 'ORDER_STATUS_UPDATE' },
  { label: '报名审核', value: 'ORDER_APPLICATION_AUDIT' },
  { label: '内容状态', value: 'CONTENT_STATUS_UPDATE' },
  { label: '删除内容', value: 'CONTENT_DELETE' },
  { label: '删除资源', value: 'FILE_DELETE' },
  { label: '删除AI会话', value: 'AI_CONVERSATION_DELETE' },
  { label: '删除AI记忆', value: 'AI_MEMORY_DELETE' },
  { label: '更新设置', value: 'SETTINGS_UPDATE' }
]

const activityMap = {
  BASKETBALL: '篮球',
  BADMINTON: '羽毛球',
  MEAL: '吃饭',
  STUDY: '自习',
  MOVIE: '看电影',
  RUNNING: '跑步',
  GAME: '游戏',
  OTHER: '其他'
}

const campusMap = {
  LIANGXIANG: '良乡校区',
  ZHONGGUANCUN: '中关村校区',
  ZHUHAI: '珠海校区',
  XISHAN: '西山校区',
  OTHER_CAMPUS: '其他校区'
}

const activityTypeOptions = Object.entries(activityMap).map(([value, label]) => ({ value, label }))
const campusOptions = Object.entries(campusMap).map(([value, label]) => ({ value, label }))

const normalizeUserType = (value) => {
  if (value === 1 || value === '1') return 'ADMIN'
  if (value === 0 || value === '0') return 'COMMON'
  return value || 'COMMON'
}

const normalizePage = (payload) => {
  const data = payload?.data || {}
  rows.value = Array.isArray(data.list) ? data.list : Array.isArray(data) ? data : []
  pagination.total = Number(data.total || rows.value.length || 0)
  pagination.page = Number(data.page || pagination.page)
  pagination.size = Number(data.size || pagination.size)
}

const clampPageSize = (value) => {
  const numeric = Number(value || 20)
  return Math.min(Math.max(numeric, 10), 50)
}

const applyAdminPreferences = () => {
  if (hasPagination.value) {
    pagination.size = clampPageSize(settings.pageSize)
  }
}

const loadSettings = async ({ applyPreferences = false } = {}) => {
  const payload = await getAdminSettings()
  Object.assign(settings, payload.data || {})
  settingsLoaded.value = true
  if (applyPreferences) {
    applyAdminPreferences()
  }
}

const ensureSettingsLoaded = async () => {
  if (!settingsLoaded.value) {
    await loadSettings({ applyPreferences: true })
  }
}

const loadApplications = async () => {
  if (mode.value !== 'orders') {
    applicationRows.value = []
    return
  }

  applicationLoading.value = true
  try {
    const params = {
      page: 1,
      size: 8,
      keyword: keyword.value || undefined
    }
    if (applicationStatus.value) params.status = applicationStatus.value
    const payload = await getAdminOrderApplications(params)
    const data = payload?.data || {}
    applicationRows.value = Array.isArray(data.list) ? data.list : Array.isArray(data) ? data : []
  } finally {
    applicationLoading.value = false
  }
}

const loadData = async () => {
  loading.value = true
  try {
    await ensureSettingsLoaded()
    if (mode.value === 'users') {
      const params = {
        page: pagination.page,
        size: pagination.size,
        keyword: keyword.value || undefined
      }
      if (userTypeFilter.value) params.userType = userTypeFilter.value
      if (userStatusFilter.value) params.userStatus = userStatusFilter.value
      const payload = await getAdminUsers(params)
      normalizePage(payload)
      rows.value = rows.value.map((row) => ({ ...row, userType: normalizeUserType(row.userType) }))
    } else if (mode.value === 'orders') {
      const params = {
        page: pagination.page,
        size: pagination.size,
        keyword: keyword.value || undefined
      }
      if (orderStatus.value) params.status = orderStatus.value
      if (orderActivityType.value) params.activityType = orderActivityType.value
      if (orderCampus.value) params.campus = orderCampus.value
      normalizePage(await getAdminOrders(params))
      await loadApplications()
    } else if (mode.value === 'contents' || mode.value === 'comments') {
      const params = {
        page: pagination.page,
        size: pagination.size,
        type: mode.value === 'comments' ? 'COMMENT' : 'POST',
        keyword: keyword.value || undefined
      }
      if (contentStatus.value) params.status = contentStatus.value
      normalizePage(await getAdminContents(params))
    } else if (mode.value === 'ai') {
      const params = {
        page: pagination.page,
        size: pagination.size,
        keyword: keyword.value || undefined
      }
      normalizePage(await getAdminAiAuditItems(params))
    } else if (mode.value === 'files') {
      const params = {
        page: pagination.page,
        size: pagination.size,
        keyword: keyword.value || undefined
      }
      if (fileType.value) params.mediaType = fileType.value
      normalizePage(await getAdminFiles(params))
    } else if (mode.value === 'logs') {
      const params = {
        page: pagination.page,
        size: pagination.size,
        keyword: keyword.value || undefined
      }
      if (auditModule.value) params.moduleName = auditModule.value
      if (auditAction.value) params.action = auditAction.value
      normalizePage(await getAdminAuditLogs(params))
    } else if (mode.value === 'settings') {
      rows.value = []
      pagination.total = 0
    } else {
      rows.value = []
      pagination.total = 0
    }
  } finally {
    loading.value = false
  }
}

const handlePageSizeChange = () => {
  pagination.page = 1
  loadData()
}

const handleFilterChange = () => {
  pagination.page = 1
  loadData()
}

const handleKeywordSearch = () => {
  pagination.page = 1
  loadData()
}

const filteredRows = computed(() => {
  if (!keyword.value) return rows.value
  if (serverKeywordModes.includes(mode.value)) return rows.value
  const q = keyword.value.toLowerCase()
  return rows.value.filter((row) => JSON.stringify(row).toLowerCase().includes(q))
})

const showMobileCards = computed(() => hasPagination.value && filteredRows.value.length > 0)
const showMobileEmpty = computed(() => hasPagination.value && !loading.value && filteredRows.value.length === 0)

const activityLabel = (value) => activityMap[value] || value || '-'
const campusLabel = (value) => campusMap[value] || value || '-'
const fileTypeLabel = (value) => ({ IMAGE: '图片', VIDEO: '视频' }[value] || value || '-')
const auditActionLabel = (value) => auditActionOptions.find((item) => item.value === value)?.label || value || '-'
const auditTargetLabel = (row) => (row?.targetId ? `#${row.targetId}` : '全局')
const applicationStatusLabel = (value) => applicationStatusOptions.find((item) => item.value === value)?.label || value || '-'
const applicationTone = (value) => ({
  PENDING_REVIEW: 'warning',
  APPROVED: 'success',
  REJECTED: 'danger',
  CANCELLED_APPLY: 'info'
}[value] || 'info')
const contentStatusLabel = (value) => contentStatusOptions.find((item) => item.value === value)?.label || value || '-'
const contentStatusTone = (value) => ({
  NORMAL: 'success',
  PENDING: 'warning',
  REJECTED: 'danger',
  DELETED: 'info'
}[value] || 'info')
const userStatusLabel = (value) => userStatusOptions.find((item) => item.value === value)?.label || value || '-'
const statusTone = (value) => ({
  ONLINE: 'success',
  OFFLINE: 'info',
  BANNED: 'danger',
  REGISTERING: 'warning'
}[value] || 'info')

const isCurrentAdminUser = (row) => Number(row?.id || 0) === currentAdminUserId.value
const isSelfBanOption = (row, value) => isCurrentAdminUser(row) && value === 'BANNED'

const resolveFileUrl = (url) => {
  if (!url) return ''
  if (/^https?:\/\//.test(url)) return url
  return url.startsWith('/') ? url : `/${url}`
}

const formatDateTime = (value) => {
  if (!value) return '-'
  return String(value).replace('T', ' ').replace(/\.\d+$/, '')
}

const mobileRowKey = (row) => row.id || row.pmid || row.cid || row.memId || JSON.stringify(row)

const isAiMemory = (row) => row.category === '记忆' || Boolean(row.memId && !row.cid)
const aiRecordId = (row) => (isAiMemory(row) ? row.memId || row.id : row.cid || row.id)
const aiRoleLabel = (role) => ({
  user: '用户',
  assistant: 'AI助手',
  system: '系统',
  tool: '工具'
}[role] || role || '消息')

const mobileInitial = (row) => {
  if (mode.value === 'orders') return String(activityLabel(row.activityType) || '活').slice(0, 1)
  if (mode.value === 'files') return row.mediaType === 'VIDEO' ? 'V' : 'I'
  if (mode.value === 'ai') return isAiMemory(row) ? '记' : 'AI'
  if (mode.value === 'logs') return '审'
  return String(row.nickname || row.user?.nickname || row.email || row.content || '项').slice(0, 1)
}

const mobileTitle = (row) => {
  if (mode.value === 'users') return row.nickname || row.email || `用户 #${row.id}`
  if (mode.value === 'orders') return `${activityLabel(row.activityType)} · ${row.location || '未填写地点'}`
  if (mode.value === 'files') return row.filename || row.url || `资源 #${row.pmid}`
  if (mode.value === 'ai') return row.title || row.content || row.summary || `会话 #${row.id || row.cid || '-'}`
  if (mode.value === 'logs') return row.actionLabel || auditActionLabel(row.action)
  return row.content || `内容 #${row.id}`
}

const mobileSubtitle = (row) => {
  if (mode.value === 'users') return row.email || `ID ${row.id}`
  if (mode.value === 'orders') return `${row.user?.nickname || '未知用户'} / ${formatDateTime(row.startTime)}`
  if (mode.value === 'files') return row.url || '未记录资源路径'
  if (mode.value === 'ai') return row.user?.email || formatDateTime(row.updatedAt || row.createdAt)
  if (mode.value === 'logs') return `${row.moduleName || '-'} / ${formatDateTime(row.createdAt)}`
  return `${row.user?.nickname || '未知用户'} / ${formatDateTime(row.createdAt)}`
}

const mobileBadge = (row) => {
  if (mode.value === 'users') return userStatusLabel(row.userStatus)
  if (mode.value === 'orders') return orderStatusOptions.find((item) => item.value === row.status)?.label || row.status || '-'
  if (mode.value === 'files') return fileTypeLabel(row.mediaType)
  if (mode.value === 'ai') return row.category || '会话'
  if (mode.value === 'logs') return row.moduleName || '审计'
  return contentStatusLabel(row.status)
}

const mobileMeta = (row) => {
  if (mode.value === 'users') {
    return [
      { label: 'ID', value: row.id || '-' },
      { label: '角色', value: normalizeUserType(row.userType) === 'ADMIN' ? '管理员' : '普通用户' },
      { label: '注册时间', value: formatDateTime(row.createdAt) }
    ]
  }
  if (mode.value === 'orders') {
    return [
      { label: 'ID', value: row.id || '-' },
      { label: '校区', value: campusLabel(row.campus) },
      { label: '人数', value: `${row.currentPeople || 0}/${row.maxPeople || 0}` }
    ]
  }
  if (mode.value === 'files') {
    return [
      { label: 'ID', value: row.pmid || '-' },
      { label: '大小', value: formatFileSize(row.size) },
      { label: '来源', value: row.user?.nickname || row.user?.email || '-' }
    ]
  }
  if (mode.value === 'ai') {
    return [
      { label: '用户', value: row.user?.nickname || row.user?.email || '-' },
      { label: isAiMemory(row) ? '分类' : '消息', value: isAiMemory(row) ? row.memoryCategory || row.source || '-' : `${row.messageCount ?? 0} 条` },
      { label: '时间', value: formatDateTime(row.updatedAt || row.createdAt) }
    ]
  }
  if (mode.value === 'logs') {
    return [
      { label: '目标', value: `${row.targetType || '-'} ${auditTargetLabel(row)}` },
      { label: '操作者', value: row.operator?.nickname || row.operator?.email || '-' },
      { label: '来源 IP', value: row.ipAddress || '-' },
      { label: '详情', value: row.detail || '-' }
    ]
  }
  return [
    { label: 'ID', value: row.id || '-' },
    { label: '互动', value: `${row.likeCount || 0} 赞 / ${row.commentCount || 0} 评` },
    { label: '媒体', value: row.mediaType || 'TEXT' },
    { label: mode.value === 'comments' ? '回复' : '关联', value: row.parent?.content || row.order?.location || '-' }
  ]
}

const formatFileSize = (value) => {
  if (!value) return '-'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

const isUserCancel = (error) => {
  const action = typeof error === 'string' ? error : error?.action
  return action === 'cancel' || action === 'close'
}

const adminErrorMessage = (error) => error?.response?.data?.message || error?.message || '操作失败，请稍后重试'

const refreshAfterFailedMutation = async () => {
  try {
    await loadData()
  } catch (refreshError) {
    console.error('刷新后台数据失败', refreshError)
  }
}

const runAdminMutation = async (action, successMessage, { refresh = true } = {}) => {
  try {
    await action()
    if (successMessage) {
      ElMessage.success(successMessage)
    }
    if (refresh) {
      await loadData()
    }
    return true
  } catch (error) {
    if (refresh) {
      await refreshAfterFailedMutation()
    }
    if (!isUserCancel(error)) {
      ElMessage.error(adminErrorMessage(error))
    }
    return false
  }
}

const updateUserRole = async (row, userType) => {
  await runAdminMutation(
    () => updateAdminUserType(row.id, userType),
    '用户权限已更新'
  )
}

const updateUserStatus = async (row, userStatus) => {
  await runAdminMutation(
    () => updateAdminUserStatus(row.id, userStatus),
    '用户状态已更新'
  )
}

const updateOrder = async (row, status) => {
  await runAdminMutation(
    () => updateAdminOrderStatus(row.id, status),
    '订单状态已更新'
  )
}

const updateContent = async (row, status) => {
  await runAdminMutation(async () => {
    if (status === 'DELETED') {
      await confirmDangerAction('确认将该内容标记为删除？删除后前台将不再展示。')
    }
    await updateAdminContentStatus(row.id, status)
  }, '内容状态已更新')
}

const auditApplication = async (row, status) => {
  await runAdminMutation(
    () => auditAdminOrderApplication(row.id, status),
    status === 'APPROVED' ? '申请已通过' : '申请已驳回'
  )
}

const confirmDangerAction = async (message) => {
  if (!settings.confirmActions) {
    return
  }

  await ElMessageBox.confirm(message, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  })
}

const removeContent = async (row) => {
  await runAdminMutation(async () => {
    await confirmDangerAction('确认删除该内容？删除后前台将不再展示。')
    await deleteAdminContent(row.id)
  }, '内容已删除')
}

const restoreContent = async (row) => {
  await runAdminMutation(
    () => updateAdminContentStatus(row.id, 'NORMAL'),
    '内容已恢复'
  )
}

const removeFile = async (row) => {
  await runAdminMutation(async () => {
    await confirmDangerAction('确认删除该文件资源？关联媒体记录也会被移除。')
    await deleteAdminFile(row.pmid)
  }, '文件资源已删除')
}

const openAiConversation = async (row) => {
  if (isAiMemory(row)) {
    return
  }

  aiDrawerVisible.value = true
  aiDetailLoading.value = true
  aiDetail.conversation = { ...row }
  aiDetail.messages = []
  try {
    const payload = await getAdminAiConversationMessages(aiRecordId(row))
    const data = payload?.data || {}
    aiDetail.conversation = data.conversation || row
    aiDetail.messages = Array.isArray(data.messages) ? data.messages : []
  } catch (error) {
    aiDrawerVisible.value = false
    aiDetail.conversation = null
    aiDetail.messages = []
    ElMessage.error(adminErrorMessage(error))
  } finally {
    aiDetailLoading.value = false
  }
}

const removeAiRecord = async (row) => {
  const memory = isAiMemory(row)
  await runAdminMutation(async () => {
    await confirmDangerAction(memory
      ? '确认删除该 AI 长期记忆？删除后不会再参与后续助手上下文。'
      : '确认删除该 AI 会话及全部消息？此操作不可恢复。'
    )

    if (memory) {
      await deleteAdminAiMemory(aiRecordId(row))
    } else {
      await deleteAdminAiConversation(aiRecordId(row))
    }

    if (!memory && aiDetail.conversation?.cid === aiRecordId(row)) {
      aiDrawerVisible.value = false
      aiDetail.conversation = null
      aiDetail.messages = []
    }
  }, memory ? 'AI记忆已删除' : 'AI会话已删除')
}

const saveSettings = async () => {
  loading.value = true
  try {
    const payload = await updateAdminSettings({ ...settings })
    Object.assign(settings, payload.data || {})
    applyAdminPreferences()
    ElMessage.success('系统设置已保存')
  } catch (error) {
    ElMessage.error(adminErrorMessage(error))
    await loadSettings({ applyPreferences: true }).catch((refreshError) => {
      console.error('刷新系统设置失败', refreshError)
    })
  } finally {
    loading.value = false
  }
}

watch(mode, () => {
  pagination.page = 1
  applyAdminPreferences()
  keyword.value = typeof route.query.q === 'string' ? route.query.q : ''
  userTypeFilter.value = ''
  userStatusFilter.value = ''
  fileType.value = ''
  contentStatus.value = ''
  auditModule.value = ''
  auditAction.value = ''
  if (mode.value === 'orders') {
    applicationStatus.value = ''
  } else {
    applicationRows.value = []
  }
  if (mode.value !== 'ai') {
    aiDrawerVisible.value = false
    aiDetail.conversation = null
    aiDetail.messages = []
  }
  loadData()
})

watch(
  () => route.query.q,
  (value) => {
    keyword.value = typeof value === 'string' ? value : ''
    pagination.page = 1
    if (serverKeywordModes.includes(mode.value)) {
      loadData()
    }
  }
)

onMounted(loadData)
</script>

<style scoped>
.admin-mobile-cards,
.admin-mobile-empty,
.application-mobile-empty {
  display: none;
}

.application-mobile-cards {
  display: none;
}

.guarded-control {
  display: inline-block;
  width: 100%;
}

.guarded-control :deep(.el-select) {
  width: 100%;
}

.admin-table-compact :deep(.el-table__cell) {
  padding: 8px 0;
}

.admin-table-compact :deep(.cell) {
  line-height: 1.35;
}

.status-select {
  width: 110px;
}

.status-select :deep(.el-select__wrapper) {
  border-color: rgba(148, 163, 184, 0.24);
  background: rgba(15, 23, 42, 0.18);
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.status-select.success :deep(.el-select__wrapper) {
  border-color: rgba(34, 197, 94, 0.36);
}

.status-select.danger :deep(.el-select__wrapper) {
  border-color: rgba(239, 68, 68, 0.42);
  box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.08);
}

.status-select.warning :deep(.el-select__wrapper) {
  border-color: rgba(245, 158, 11, 0.4);
}

.status-select.info :deep(.el-select__wrapper) {
  border-color: rgba(100, 116, 139, 0.36);
}

.ai-table-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-table-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.ai-audit-drawer {
  max-width: 100vw;
}

.ai-audit-drawer :deep(.el-drawer__header) {
  margin-bottom: 0;
  padding: 18px 20px 14px;
  border-bottom: 1px solid var(--ch-border);
}

.ai-audit-drawer :deep(.el-drawer__body) {
  padding: 18px 20px 22px;
  background: var(--ch-bg);
}

.ai-detail {
  min-height: 260px;
}

.ai-detail-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.ai-detail-summary > div {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--ch-border);
  border-radius: 14px;
  background: var(--ch-surface-solid);
}

.ai-detail-summary span,
.ai-detail-summary strong {
  display: block;
}

.ai-detail-summary span {
  color: var(--ch-muted);
  font-size: 12px;
  line-height: 1.4;
}

.ai-detail-summary strong {
  margin-top: 4px;
  color: var(--ch-text);
  font-size: 13px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.ai-message-list {
  display: grid;
  gap: 12px;
}

.ai-message-card {
  padding: 14px;
  border: 1px solid var(--ch-border);
  border-radius: 16px;
  background: var(--ch-surface-solid);
}

.ai-message-card.user {
  border-color: rgba(59, 130, 246, 0.26);
  background: rgba(59, 130, 246, 0.08);
}

.ai-message-card.assistant {
  border-color: rgba(20, 184, 166, 0.24);
  background: rgba(20, 184, 166, 0.08);
}

.ai-message-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.ai-message-head strong {
  color: var(--ch-text);
  font-size: 13px;
}

.ai-message-head span,
.ai-message-meta {
  color: var(--ch-muted);
  font-size: 12px;
}

.ai-message-card p {
  margin: 0;
  color: var(--ch-text);
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.ai-message-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.order-audit-section {
  margin-top: 24px;
  padding-top: 22px;
  border-top: 1px solid var(--ch-border);
}

.audit-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 16px;
}

.audit-section-head strong {
  display: block;
  color: var(--ch-text);
  font-size: 16px;
  line-height: 1.35;
}

.audit-section-head p {
  margin: 4px 0 0;
  color: var(--ch-muted);
  font-size: 13px;
  line-height: 1.5;
}

.audit-section-tools {
  display: flex;
  align-items: center;
  gap: 10px;
}

.audit-section-tools :deep(.el-select) {
  width: 150px;
}

@media (max-width: 620px) {
  .admin-page :deep(.admin-table) {
    display: none;
  }

  .admin-mobile-cards {
    display: grid;
    gap: 12px;
  }

  .application-mobile-cards {
    display: grid;
    gap: 12px;
  }

  .admin-mobile-empty {
    display: block;
  }

  .application-mobile-empty {
    display: block;
  }

  .admin-mobile-card {
    padding: 14px;
    border: 1px solid var(--ch-border);
    border-radius: 14px;
    background: var(--ch-surface-solid);
  }

  .admin-mobile-card-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
  }

  .admin-mobile-identity {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .admin-mobile-identity > div {
    min-width: 0;
  }

  .admin-mobile-identity strong {
    display: block;
    color: var(--ch-text);
    font-size: 15px;
    line-height: 1.35;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .admin-mobile-identity p {
    margin: 3px 0 0;
    color: var(--ch-muted);
    font-size: 12px;
    line-height: 1.4;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .admin-mobile-meta {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    padding: 12px;
    border-radius: 12px;
    background: var(--ch-bg-soft);
  }

  .admin-mobile-meta span,
  .admin-mobile-meta strong {
    display: block;
  }

  .admin-mobile-meta span {
    color: var(--ch-muted);
    font-size: 12px;
  }

  .admin-mobile-meta strong {
    margin-top: 4px;
    color: var(--ch-text);
    font-size: 13px;
    line-height: 1.35;
    word-break: break-word;
  }

  .admin-mobile-actions {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 8px;
    margin-top: 12px;
  }

  .admin-mobile-actions :deep(.el-button),
  .admin-mobile-actions :deep(.el-select) {
    width: 100%;
    margin-left: 0;
  }

  .admin-mobile-actions .status-select {
    width: 100%;
    min-width: 0;
  }

  .ai-detail-summary {
    grid-template-columns: 1fr;
  }

  .content-mobile-card .admin-mobile-identity {
    align-items: flex-start;
  }

  .content-mobile-card .admin-mobile-identity strong,
  .content-mobile-card .admin-mobile-identity p {
    white-space: normal;
  }

  .content-mobile-card .admin-mobile-identity strong {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .content-mobile-card .admin-mobile-actions {
    grid-template-columns: minmax(0, 1fr) minmax(92px, auto);
  }

  .audit-section-head,
  .audit-section-tools {
    display: grid;
    width: 100%;
  }

  .audit-section-tools :deep(.el-select) {
    width: 100%;
  }

  .application-card {
    padding: 14px;
    border: 1px solid var(--ch-border);
    border-radius: 14px;
    background: var(--ch-surface-solid);
  }

  .application-card-head {
    display: flex;
    justify-content: space-between;
    gap: 12px;
  }

  .application-card-head strong {
    display: block;
    color: var(--ch-text);
    font-size: 14px;
    line-height: 1.4;
  }

  .application-card-head p,
  .application-card-meta {
    color: var(--ch-muted);
    font-size: 12px;
    line-height: 1.45;
  }

  .application-card-head p {
    margin: 4px 0 0;
  }

  .application-card-meta {
    display: grid;
    gap: 4px;
    margin-top: 12px;
  }

  .admin-pagination {
    overflow: hidden;
  }

  .admin-pagination :deep(.el-pagination) {
    justify-content: center;
    max-width: 100%;
  }
}
</style>
